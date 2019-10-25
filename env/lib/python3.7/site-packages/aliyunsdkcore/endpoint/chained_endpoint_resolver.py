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

from aliyunsdkcore.acs_exception.exceptions import ClientException
from aliyunsdkcore.endpoint import EndpointResolver

import aliyunsdkcore.acs_exception.error_code as error_code
import aliyunsdkcore.acs_exception.error_msg as error_msg


class ChainedEndpointResolver(EndpointResolver):

    def __init__(self, resolver_chain):
        EndpointResolver.__init__(self)
        self.endpoint_resolvers = resolver_chain

    def _check_product_code(self, request):
        for resolver in self.endpoint_resolvers:
            if resolver.is_product_code_valid(request):
                return

        raise ClientException(
            error_code.SDK_ENDPOINT_RESOLVING_ERROR,
            error_msg.ENDPOINT_NO_PRODUCT.format(
                product_code=request.product_code)
        )

    def _check_region_id(self, request):
        for resolver in self.endpoint_resolvers:
            if resolver.is_region_id_valid(request):
                return

        raise ClientException(
            error_code.SDK_ENDPOINT_RESOLVING_ERROR,
            error_msg.INVALID_REGION_ID.format(region_id=request.region_id)
        )

    def _get_available_regions_hint(self, product_code):
        regions = None
        hint = ""
        for resolver in self.endpoint_resolvers:
            regions = resolver.get_valid_region_ids_by_product(product_code)
            if regions is not None:
                hint = "\nOr you can use the other available regions:"
                for region in regions:
                    hint += " " + region
                break
        return hint

    def resolve(self, request):
        for resolver in self.endpoint_resolvers:
            endpoint = resolver.resolve(request)
            if endpoint is not None:
                return endpoint

        self._check_product_code(request)
        self._check_region_id(request)

        raise ClientException(
            error_code.SDK_ENDPOINT_RESOLVING_ERROR,
            error_msg.ENDPOINT_NO_REGION.format(
                region_id=request.region_id,
                product_code=request.product_code,
                more=self._get_available_regions_hint(request.product_code)
            )
        )
