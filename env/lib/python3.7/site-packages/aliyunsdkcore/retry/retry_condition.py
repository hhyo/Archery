# Copyright 2019 Alibaba Cloud Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import jmespath
import logging

import aliyunsdkcore.utils
import aliyunsdkcore.utils.validation as validation
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
import aliyunsdkcore.acs_exception.error_code as error_code

logger = logging.getLogger(__name__)


def _find_data_in_retry_config(key_name, request, retry_config):
    if request.get_product() is None:
        return None
    path = '"{0}"."{1}"."{2}"'.format(request.get_product().lower(),
                                      request.get_version(),
                                      key_name)
    return jmespath.search(path, retry_config)


class RetryCondition(object):

    BLANK_STATUS = 0
    NO_RETRY = 1
    SHOULD_RETRY = 2
    SHOULD_RETRY_WITH_CLIENT_TOKEN = 4
    SHOULD_RETRY_WITH_THROTTLING_BACKOFF = 8

    def should_retry(self, retry_policy_context):
        """Decide whether the previous request should be retried."""
        pass


class NoRetryCondition(RetryCondition):

    def should_retry(self, retry_policy_context):
        return RetryCondition.NO_RETRY


class MaxRetryTimesCondition(RetryCondition):

    def __init__(self, max_retry_times):
        validation.assert_integer_positive(max_retry_times, "max_retry_times")
        self.max_retry_times = max_retry_times

    def should_retry(self, retry_policy_context):

        if retry_policy_context.retries_attempted < self.max_retry_times:
            return RetryCondition.SHOULD_RETRY
        else:
            logger.debug("Reached the maximum number of retry. Attempts:%d",
                         retry_policy_context.retries_attempted)
            return RetryCondition.NO_RETRY


class RetryOnExceptionCondition(RetryCondition):

    def __init__(self, retry_config):
        self.retry_config = retry_config

    def should_retry(self, retry_policy_context):
        request = retry_policy_context.original_request
        exception = retry_policy_context.exception

        if isinstance(exception, ClientException):
            if exception.get_error_code() == error_code.SDK_HTTP_ERROR:

                logger.debug("Retryable ClientException occurred. ClientException:%s",
                             exception)
                return RetryCondition.SHOULD_RETRY

        if isinstance(exception, ServerException):
            error_code_ = exception.get_error_code()
            normal_errors = _find_data_in_retry_config("RetryableNormalErrors",
                                                       request,
                                                       self.retry_config)
            if isinstance(normal_errors, list) and error_code_ in normal_errors:
                logger.debug("Retryable ServerException occurred. ServerException:%s",
                             exception)
                return RetryCondition.SHOULD_RETRY

            throttling_errors = _find_data_in_retry_config("RetryableThrottlingErrors",
                                                           request,
                                                           self.retry_config)
            if isinstance(throttling_errors, list) and error_code_ in throttling_errors:
                logger.debug("Retryable ThrottlingError occurred. ThrottlingError:%s",
                             exception)
                return RetryCondition.SHOULD_RETRY | \
                    RetryCondition.SHOULD_RETRY_WITH_THROTTLING_BACKOFF

        return RetryCondition.NO_RETRY


class RetryOnHttpStatusCondition(RetryCondition):

    DEFAULT_RETRYABLE_HTTP_STATUS_LIST = [
        500, 502, 503, 504
    ]

    def __init__(self, retryable_http_status_list=None):
        if retryable_http_status_list:
            self.retryable_http_status_list = retryable_http_status_list
        else:
            self.retryable_http_status_list = self.DEFAULT_RETRYABLE_HTTP_STATUS_LIST

    def should_retry(self, retry_policy_context):
        if retry_policy_context.http_status_code in self.retryable_http_status_list:
            logger.debug(
                "Retryable HTTP error occurred. HTTP status code: %s",
                retry_policy_context.http_status_code)
            return RetryCondition.SHOULD_RETRY
        else:
            return RetryCondition.NO_RETRY


class RetryOnApiCondition(RetryCondition):

    def __init__(self, retry_config):
        self.retry_config = retry_config

    def should_retry(self, retry_policy_context):
        request = retry_policy_context.original_request
        retryable_apis = _find_data_in_retry_config("RetryableAPIs", request, self.retry_config)
        if isinstance(retryable_apis, list) and request.get_action_name() in retryable_apis:
            return RetryCondition.SHOULD_RETRY
        else:
            return RetryCondition.NO_RETRY


class RetryOnApiWithClientTokenCondition(RetryCondition):

    def __init__(self, retry_config):
        self.retry_config = retry_config

    def should_retry(self, retry_policy_context):
        request = retry_policy_context.original_request
        retryable_apis = _find_data_in_retry_config(
            "RetryableAPIsWithClientToken", request, self.retry_config)
        if isinstance(retryable_apis, list) and request.get_action_name() in retryable_apis:
            return RetryCondition.SHOULD_RETRY | RetryCondition.SHOULD_RETRY_WITH_THROTTLING_BACKOFF
        else:
            return RetryCondition.NO_RETRY


class AndRetryCondition(RetryCondition):

    def __init__(self, conditions):
        self.conditions = conditions

    def should_retry(self, retry_policy_context):
        retryable = RetryCondition.BLANK_STATUS
        for condition in self.conditions:
            retryable |= condition.should_retry(retry_policy_context)
        return retryable


class OrRetryCondition(RetryCondition):

    def __init__(self, conditions):
        self.conditions = conditions

    def should_retry(self, retry_policy_context):
        retryable = RetryCondition.BLANK_STATUS
        no_retry_flag = RetryCondition.NO_RETRY
        mask = RetryCondition.SHOULD_RETRY
        mask |= RetryCondition.SHOULD_RETRY_WITH_CLIENT_TOKEN
        mask |= RetryCondition.SHOULD_RETRY_WITH_THROTTLING_BACKOFF

        for condition in self.conditions:
            ret = condition.should_retry(retry_policy_context)
            retryable |= ret & mask
            no_retry_flag &= ret & RetryCondition.NO_RETRY
        return retryable | no_retry_flag


class MixedRetryCondition(RetryCondition):

    def __init__(self, max_retry_times, retry_config):
        RetryCondition.__init__(self)
        self._inner_condition = AndRetryCondition([
            MaxRetryTimesCondition(max_retry_times),
            OrRetryCondition([
                RetryOnApiCondition(retry_config),
                RetryOnApiWithClientTokenCondition(retry_config),
            ]),
            OrRetryCondition([
                RetryOnExceptionCondition(retry_config),
                RetryOnHttpStatusCondition(),
            ]),
        ])

    def should_retry(self, retry_policy_context):
        return self._inner_condition.should_retry(retry_policy_context)


class DefaultConfigRetryCondition(MixedRetryCondition):

    DEFAULT_MAX_RETRY_TIMES = 3
    RETRY_CONFIG_FILE = "retry_config.json"
    _loaded_retry_config = None

    def __init__(self, max_retry_times=None):
        if not self._loaded_retry_config:
            self._loaded_retry_config = aliyunsdkcore.utils._load_json_from_data_dir(
                self.RETRY_CONFIG_FILE)

        if max_retry_times is None:
            max_retry_times = self.DEFAULT_MAX_RETRY_TIMES
        MixedRetryCondition.__init__(self, max_retry_times, self._loaded_retry_config)
