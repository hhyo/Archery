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
from aliyunsdkcore.endpoint.endpoint_resolver_base import EndpointResolverBase


class UserCustomizedEndpointResolver(EndpointResolverBase):

    def __init__(self):
        EndpointResolverBase.__init__(self)
        self._valid_region_ids = set()

    def put_endpoint_entry(self, region_id, product_code, endpoint):
        EndpointResolverBase.put_endpoint_entry(
            self, self._make_endpoint_entry_key(product_code, region_id), endpoint)
        self._valid_region_ids.add(region_id)

    def resolve(self, request):
        return self.fetch_endpoint_entry(request)

    def get_endpoint_key_from_request(self, request):
        return self._make_endpoint_entry_key(request.product_code, request.region_id)

    def _make_endpoint_entry_key(self, product_code, region_id):
        return product_code.lower() + "." + region_id.lower()

    def is_region_id_valid(self, request):
        return request.region_id in self._valid_region_ids

    def reset(self):
        self.endpoints_data = dict()
