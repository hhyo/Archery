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

ENDPOINT_TYPE_INNER = "innerAPI"
ENDPOINT_TYPE_OPEN = "openAPI"


class ResolveEndpointRequest(object):

    def __init__(self, region_id, product_code, location_service_code, endpoint_type):

        self.region_id = region_id
        self.product_code = product_code
        self.product_code_lower = self.product_code.lower()

        if not endpoint_type:
            self.endpoint_type = ENDPOINT_TYPE_OPEN
        else:
            self.endpoint_type = endpoint_type

        self.location_service_code = location_service_code

        self.request_network = "public"
        self.product_suffix = ""
        self.endpoint_map = None
        self.endpoint_regional = None

    def is_open_api_endpoint(self):
        return ENDPOINT_TYPE_OPEN == self.endpoint_type

