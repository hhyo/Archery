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

import os.path
import json

import aliyunsdkcore
from aliyunsdkcore.vendored.six import iteritems
from aliyunsdkcore.endpoint.endpoint_resolver_base import EndpointResolverBase
from aliyunsdkcore.endpoint.resolver_endpoint_request import ResolveEndpointRequest


class LocalConfigRegionalEndpointResolver(EndpointResolverBase):

    ENDPOINT_JSON = os.path.join(os.path.dirname(aliyunsdkcore.__file__),
                                 "data", "endpoints.json")

    def __init__(self, config_json_str=None):
        EndpointResolverBase.__init__(self)
        self._valid_region_ids = []
        self._location_code_mapping = dict()
        self._regional_endpoint_data = dict()
        if config_json_str:
            obj = json.loads(config_json_str)
        else:
            obj = self._read_from_endpoints_json()
        self._init_local_config(obj)

    def _init_local_config(self, obj):
        self._init_regional_endpoint_data(obj)
        self._init_region_ids(obj)
        self._init_location_code_mapping(obj)

    def _init_regional_endpoint_data(self, obj):
        if "regional_endpoints" not in obj:
            return
        self._regional_endpoint_data = obj["regional_endpoints"]
        for code, product_data in iteritems(obj["regional_endpoints"]):
            for region_id, endpoint in iteritems(product_data):
                self.put_endpoint_entry(self._make_endpoint_entry_key(code, region_id), endpoint)

    def _init_region_ids(self, obj):
        if "regions" not in obj:
            return
        self._valid_region_ids = obj["regions"]

    def _init_location_code_mapping(self, obj):
        if "location_code_mapping" not in obj:
            return
        self._location_code_mapping = obj["location_code_mapping"]

    def _get_normalized_product_code(self, product_code):
        product_code_lower = product_code.lower()
        if product_code_lower in self._location_code_mapping:
            return self._location_code_mapping.get(product_code_lower)
        return product_code_lower

    def _read_from_endpoints_json(self):
        with open(self.ENDPOINT_JSON) as fp:
            return json.loads(fp.read())

    def resolve(self, request):
        if request.is_open_api_endpoint():
            return self.fetch_endpoint_entry(request)
        else:
            return None

    def get_endpoint_key_from_request(self, request):
        return self._make_endpoint_entry_key(request.product_code_lower, request.region_id)

    def _make_endpoint_entry_key(self, product_code, region_id):
        return self._get_normalized_product_code(product_code) + "." + region_id.lower()

    def is_region_id_valid(self, request):
        return request.region_id in self._valid_region_ids

    def get_valid_region_ids_by_product(self, product_code):
        code = self._get_normalized_product_code(product_code)
        if code in self._regional_endpoint_data:
            region_ids = self._regional_endpoint_data.get(code).keys()
            return sorted(region_ids)
        return None

    def is_product_code_valid(self, request):

        tmp_request = ResolveEndpointRequest(
            request.region_id,
            self._get_normalized_product_code(request.product_code),
            request.location_service_code,
            request.endpoint_type,
        )
        return EndpointResolverBase.is_product_code_valid(self, tmp_request)
