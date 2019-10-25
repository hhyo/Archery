# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# coding=utf-8

"""
Region&Endpoint provider module.

Created on 6/12/2015

@author: alex

modified by wenyang@2018-03-14:
    reconstruction the smelly codes and keep compatibility
"""

from aliyunsdkcore.endpoint.default_endpoint_resolver import DefaultEndpointResolver


# WARNING: Deprecated Functions!
# same as modify_point
def add_endpoint(product_name, region_id, end_point):
    modify_point(product_name, region_id, end_point)


# WARNING: Deprecated Functions!
def modify_point(product_name, region_id, end_point):
    put_endpoint_entry = DefaultEndpointResolver.predefined_endpoint_resolver.put_endpoint_entry
    put_endpoint_entry(region_id, product_name, end_point)

