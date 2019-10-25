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

import random
from aliyunsdkcore.retry.retry_condition import RetryCondition


class BackoffStrategy(object):

    def compute_delay_before_next_retry(self, retry_policy_context):
        """Compute delay for request need to be retried, in milliseconds"""
        pass


class FixedDelayStrategy(BackoffStrategy):

    def __init__(self, fixed_delay):
        self.fixed_delay = fixed_delay

    def compute_delay_before_next_retry(self, retry_policy_context):
        return self.fixed_delay


class NoDelayStrategy(FixedDelayStrategy):

    def __init__(self):
        FixedDelayStrategy.__init__(self, 0)


class ExponentialBackoffStrategy(BackoffStrategy):

    MAX_RETRY_LIMIT = 30   # to avoid integer overflow during delay calculation

    def __init__(self, base_delay_in_milliseconds, max_delay_in_milliseconds):
        self.base_delay_in_milliseconds = base_delay_in_milliseconds
        self.max_delay_in_milliseconds = max_delay_in_milliseconds

    def compute_delay_before_next_retry(self, retry_policy_context):
        retries = min(self.MAX_RETRY_LIMIT, retry_policy_context.retries_attempted)
        delay = min(self.max_delay_in_milliseconds, self.base_delay_in_milliseconds << retries)
        return delay


class JitteredExponentialBackoffStrategy(ExponentialBackoffStrategy):

    def compute_delay_before_next_retry(self, retry_policy_context):
        delay = ExponentialBackoffStrategy.compute_delay_before_next_retry(self,
                                                                           retry_policy_context)
        return delay / 2 + random.randint(0, int(delay / 2))


class DefaultMixedBackoffStrategy(BackoffStrategy):

    # in milliseconds
    SDK_DEFAULT_BASE_DELAY = 100
    SDK_DEFAULT_TROTTLED_BASE_DELAY = 500
    SDK_DEFAULT_MAX_BACKOFF = 20 * 1000

    def __init__(self):
        self._default_backoff_strategy = ExponentialBackoffStrategy(
            self.SDK_DEFAULT_BASE_DELAY,
            self.SDK_DEFAULT_MAX_BACKOFF
        )
        self._default_throttled_backoff_strategy = JitteredExponentialBackoffStrategy(
            self.SDK_DEFAULT_TROTTLED_BASE_DELAY,
            self.SDK_DEFAULT_MAX_BACKOFF
        )

    def compute_delay_before_next_retry(self, retry_policy_context):
        retryable = retry_policy_context.retryable
        if retryable & RetryCondition.SHOULD_RETRY_WITH_THROTTLING_BACKOFF:
            return self._default_throttled_backoff_strategy.compute_delay_before_next_retry(
                retry_policy_context)
        else:
            return self._default_backoff_strategy.compute_delay_before_next_retry(
                retry_policy_context)
