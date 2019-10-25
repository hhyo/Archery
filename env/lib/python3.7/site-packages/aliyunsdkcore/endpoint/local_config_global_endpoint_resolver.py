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
from aliyunsdkcore.vendored.six import iteritems

from aliyunsdkcore.endpoint.local_config_regional_endpoint_resolver \
    import LocalConfigRegionalEndpointResolver


class LocalConfigGlobalEndpointResolver(LocalConfigRegionalEndpointResolver):

    def _init_local_config(self, obj):
        self._init_global_endpoint_data(obj)
        self._init_region_ids(obj)
        self._init_location_code_mapping(obj)

    def _init_global_endpoint_data(self, obj):
        if "global_endpoints" not in obj:
            return

        global_endpoints = obj["global_endpoints"]
        for location_service_code, endpoint in iteritems(global_endpoints):
            self.put_endpoint_entry(self._make_endpoint_entry_key(location_service_code), endpoint)

    def resolve(self, request):
        if request.is_open_api_endpoint() and self.is_region_id_valid(request):
            return self.fetch_endpoint_entry(request)
        else:
            return None

    def get_endpoint_key_from_request(self, request):
        return self._make_endpoint_entry_key(request.product_code)

    def _make_endpoint_entry_key(self, product_code):
        return self._get_normalized_product_code(product_code)
