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
from aliyunsdkcore.endpoint.local_config_regional_endpoint_resolver \
    import LocalConfigRegionalEndpointResolver


class EndpointResolverRules(LocalConfigRegionalEndpointResolver):
    def __init__(self, *args, **kwargs):
        LocalConfigRegionalEndpointResolver.__init__(self)
        self.product_code_valid = False
        self.region_id_valid = False
        self.endpoint_map = None
        self.endpoint_regional = None
        self.request_network = 'public'
        self.product_suffix = ''

    def resolve(self, request):
        if request.endpoint_map is None or request.endpoint_regional is None:
            return None
        request_network = "public" if not request.request_network else request.request_network

        endpoint_regional = request.endpoint_regional
        endpoint = ""
        if request_network == "public":
            endpoint = request.endpoint_map.get(request.region_id, "")

        if endpoint == "":
            if endpoint_regional == "regional":
                if request.region_id not in self._valid_region_ids:
                    return None
                endpoint_domain = ".{region_id}.aliyuncs.com".format(
                    region_id=request.region_id.lower())
            elif endpoint_regional == "central":
                endpoint_domain = ".aliyuncs.com"
            else:
                return None

            network = "" if request_network == "public" else "-" + request_network
            suffix = "-" + request.product_suffix if request.product_suffix else ""
            endpoint_param_list = [request.product_code_lower, suffix, network, endpoint_domain]

            endpoint = "".join(list(filter(lambda x: x, endpoint_param_list)))
        return endpoint

    def is_product_code_valid(self, request):
        return self.product_code_valid

    def is_region_id_valid(self, request):
        return self.region_id_valid

    @classmethod
    def get_valid_region_ids_by_product(cls, product_code):
        return None
