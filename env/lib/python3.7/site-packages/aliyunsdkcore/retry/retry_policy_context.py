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

from aliyunsdkcore.retry.retry_condition import RetryCondition


class RetryPolicyContext:

    def __init__(self, original_request, exception, retries_attempted, http_status_code):
        self.original_request = original_request
        self.exception = exception
        self.retries_attempted = retries_attempted
        self.http_status_code = http_status_code
        self.retryable = RetryCondition.BLANK_STATUS
