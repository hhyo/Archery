# Copyright 2018 Alibaba Cloud Inc. All rights reserved.
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

from aliyunsdkcore.endpoint import EndpointResolver
from aliyunsdkcore.endpoint.chained_endpoint_resolver import ChainedEndpointResolver
from aliyunsdkcore.endpoint.user_customized_endpoint_resolver import UserCustomizedEndpointResolver
from aliyunsdkcore.endpoint.local_config_regional_endpoint_resolver \
    import LocalConfigRegionalEndpointResolver
from aliyunsdkcore.endpoint.local_config_global_endpoint_resolver \
    import LocalConfigGlobalEndpointResolver
from aliyunsdkcore.endpoint.location_service_endpoint_resolver \
    import LocationServiceEndpointResolver
from aliyunsdkcore.endpoint.endpoint_resolver_rules import EndpointResolverRules


class DefaultEndpointResolver(EndpointResolver):

    # Deprecated use for add_endpoint and modify_endpoint
    # Not recommended
    predefined_endpoint_resolver = UserCustomizedEndpointResolver()

    def __init__(self, client, user_config=None):

        self._user_customized_endpoint_resolver = UserCustomizedEndpointResolver()

        endpoint_resolvers = [
            self.predefined_endpoint_resolver,
            self._user_customized_endpoint_resolver,
            LocalConfigRegionalEndpointResolver(user_config),
            EndpointResolverRules(),
            LocalConfigGlobalEndpointResolver(user_config),
            LocationServiceEndpointResolver(client),
        ]

        self._resolver = ChainedEndpointResolver(endpoint_resolvers)

    def resolve(self, request):
        return self._resolver.resolve(request)

    def put_endpoint_entry(self, region_id, product_code, endpoint):
        self._user_customized_endpoint_resolver.put_endpoint_entry(region_id, product_code,
                                                                   endpoint)
