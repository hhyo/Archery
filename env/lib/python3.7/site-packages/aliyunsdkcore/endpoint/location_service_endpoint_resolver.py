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

import threading
import json

from aliyunsdkcore.acs_exception.exceptions import ServerException
from aliyunsdkcore.endpoint.endpoint_resolver_base import EndpointResolverBase
from aliyunsdkcore.endpoint.location.DescribeEndpointsRequest import DescribeEndpointsRequest

DEFAULT_LOCATION_SERVICE_ENDPOINT = "location-readonly.aliyuncs.com"


class LocationServiceEndpointResolver(EndpointResolverBase):

    def __init__(self, client):
        EndpointResolverBase.__init__(self)
        self._location_service_endpoint = DEFAULT_LOCATION_SERVICE_ENDPOINT
        self._client = client
        self._invalid_product_codes = set()
        self._invalid_region_ids = set()
        self._valid_product_codes = set()
        self._valid_region_ids = set()

    def set_location_service_endpoint(self, endpoint):
        self._location_service_endpoint = endpoint

    def resolve(self, request):
        if not request.location_service_code:
            return None

        if request.product_code_lower in self._invalid_product_codes:
            return None

        if request.region_id in self._invalid_region_ids:
            return None

        key = self.get_endpoint_key_from_request(request)
        if key in self.endpoints_data:
            # The endpoint can be None when last fetch is failed
            return self.endpoints_data[key]

        lock = threading.Lock()
        with lock:
            return self._get_endpoint_from_location_service(key, request)

    def _get_endpoint_from_location_service(self, key, request):
        # when other thread
        if key in self.endpoints_data:
            return self.endpoints_data.get(key)

        self._call_location_service(key, request)

        return self.endpoints_data.get(key)

    def _call_location_service(self, key, raw_request):
        request = DescribeEndpointsRequest()
        request.set_protocol_type("https")
        request.set_accept_format("json")
        request.set_Id(raw_request.region_id)
        request.set_ServiceCode(raw_request.location_service_code)
        request.set_Type(raw_request.endpoint_type)
        request.endpoint = self._location_service_endpoint

        try:
            response = self._client.do_action_with_exception(request)
        except ServerException as e:
            if "InvalidRegionId" == e.get_error_code() and \
               "The specified region does not exist." == e.get_error_msg():
                # No such region`
                self._invalid_region_ids.add(raw_request.region_id)
                self.put_endpoint_entry(key, None)
                return
            elif "Illegal Parameter" == e.get_error_code() and \
                 "Please check the parameters" == e.get_error_msg():
                # No such product
                self._invalid_product_codes.add(raw_request.product_code_lower)
                self.put_endpoint_entry(key, None)
                return
            else:
                raise e

        # As long as code gets here
        # the product code and the region id is valid
        # the endpoint can be still not found
        self._valid_product_codes.add(raw_request.product_code_lower)
        self._valid_region_ids.add(raw_request.region_id)

        found_flag = False
        body = json.loads(response.decode('utf-8'))
        for item in body["Endpoints"]["Endpoint"]:

            # Location return data has a typo: SerivceCode
            # We still try to expect ServiceCode in case this typo would be fixed in the future
            service_code = item.get("ServiceCode") or item.get("SerivceCode")

            if service_code and item.get("Type") == raw_request.endpoint_type:
                found_flag = True
                self.put_endpoint_entry(key, item.get("Endpoint"))
                break

        if not found_flag:
            self.put_endpoint_entry(key, None)

    def is_product_code_valid(self, request):
        if request.location_service_code:
            return request.product_code_lower not in self._invalid_product_codes
        return False

    def is_region_id_valid(self, request):
        if request.location_service_code:
            return request.region_id not in self._invalid_region_ids
        return False

    def get_endpoint_key_from_request(self, request):
        return self._make_endpoint_entry_key(
            request.product_code, request.location_service_code,
            request.region_id, request.endpoint_type
        )

    def _make_endpoint_entry_key(self,
                                 product_code,
                                 location_service_code,
                                 region_id, endpoint_type):
        return ".".join([
            product_code.lower(),
            location_service_code,
            region_id.lower(),
            endpoint_type
        ])
