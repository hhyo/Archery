#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with self work for additional information
# regarding copyright ownership.  The ASF licenses self file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use self file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

from aliyunsdkcore.endpoint import EndpointResolver


class EndpointResolverBase(EndpointResolver):

    def __init__(self):
        EndpointResolver.__init__(self)
        self.endpoints_data = dict()

    def fetch_endpoint_entry(self, request):
        key = self.get_endpoint_key_from_request(request)
        return self.endpoints_data.get(key)

    def put_endpoint_entry(self, key, endpoint):
        self.endpoints_data[key] = endpoint

    def is_product_code_valid(self, request):
        for key in self.endpoints_data.keys():
            if key.startswith(request.product_code_lower):
                return True
        return False

    def is_region_id_valid(self, request):
        raise NotImplementedError()

    def get_endpoint_key_from_request(self, request):
        raise NotImplementedError()

    def get_valid_region_ids_by_product(self, product_code):
        # Only local config can tell
        return None
