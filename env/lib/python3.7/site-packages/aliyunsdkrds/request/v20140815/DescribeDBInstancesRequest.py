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

from aliyunsdkcore.request import RpcRequest
class DescribeDBInstancesRequest(RpcRequest):

	def __init__(self):
		RpcRequest.__init__(self, 'Rds', '2014-08-15', 'DescribeDBInstances','rds')

	def get_ConnectionMode(self):
		return self.get_query_params().get('ConnectionMode')

	def set_ConnectionMode(self,ConnectionMode):
		self.add_query_param('ConnectionMode',ConnectionMode)

	def get_Tag4value(self):
		return self.get_query_params().get('Tag.4.value')

	def set_Tag4value(self,Tag4value):
		self.add_query_param('Tag.4.value',Tag4value)

	def get_ResourceOwnerId(self):
		return self.get_query_params().get('ResourceOwnerId')

	def set_ResourceOwnerId(self,ResourceOwnerId):
		self.add_query_param('ResourceOwnerId',ResourceOwnerId)

	def get_Tag2key(self):
		return self.get_query_params().get('Tag.2.key')

	def set_Tag2key(self,Tag2key):
		self.add_query_param('Tag.2.key',Tag2key)

	def get_ClientToken(self):
		return self.get_query_params().get('ClientToken')

	def set_ClientToken(self,ClientToken):
		self.add_query_param('ClientToken',ClientToken)

	def get_SearchKey(self):
		return self.get_query_params().get('SearchKey')

	def set_SearchKey(self,SearchKey):
		self.add_query_param('SearchKey',SearchKey)

	def get_Tag3key(self):
		return self.get_query_params().get('Tag.3.key')

	def set_Tag3key(self,Tag3key):
		self.add_query_param('Tag.3.key',Tag3key)

	def get_PageNumber(self):
		return self.get_query_params().get('PageNumber')

	def set_PageNumber(self,PageNumber):
		self.add_query_param('PageNumber',PageNumber)

	def get_Tag1value(self):
		return self.get_query_params().get('Tag.1.value')

	def set_Tag1value(self,Tag1value):
		self.add_query_param('Tag.1.value',Tag1value)

	def get_Engine(self):
		return self.get_query_params().get('Engine')

	def set_Engine(self,Engine):
		self.add_query_param('Engine',Engine)

	def get_PageSize(self):
		return self.get_query_params().get('PageSize')

	def set_PageSize(self,PageSize):
		self.add_query_param('PageSize',PageSize)

	def get_DBInstanceStatus(self):
		return self.get_query_params().get('DBInstanceStatus')

	def set_DBInstanceStatus(self,DBInstanceStatus):
		self.add_query_param('DBInstanceStatus',DBInstanceStatus)

	def get_DBInstanceId(self):
		return self.get_query_params().get('DBInstanceId')

	def set_DBInstanceId(self,DBInstanceId):
		self.add_query_param('DBInstanceId',DBInstanceId)

	def get_Tag3value(self):
		return self.get_query_params().get('Tag.3.value')

	def set_Tag3value(self,Tag3value):
		self.add_query_param('Tag.3.value',Tag3value)

	def get_proxyId(self):
		return self.get_query_params().get('proxyId')

	def set_proxyId(self,proxyId):
		self.add_query_param('proxyId',proxyId)

	def get_Tag5key(self):
		return self.get_query_params().get('Tag.5.key')

	def set_Tag5key(self,Tag5key):
		self.add_query_param('Tag.5.key',Tag5key)

	def get_ResourceOwnerAccount(self):
		return self.get_query_params().get('ResourceOwnerAccount')

	def set_ResourceOwnerAccount(self,ResourceOwnerAccount):
		self.add_query_param('ResourceOwnerAccount',ResourceOwnerAccount)

	def get_OwnerAccount(self):
		return self.get_query_params().get('OwnerAccount')

	def set_OwnerAccount(self,OwnerAccount):
		self.add_query_param('OwnerAccount',OwnerAccount)

	def get_OwnerId(self):
		return self.get_query_params().get('OwnerId')

	def set_OwnerId(self,OwnerId):
		self.add_query_param('OwnerId',OwnerId)

	def get_Tag5value(self):
		return self.get_query_params().get('Tag.5.value')

	def set_Tag5value(self,Tag5value):
		self.add_query_param('Tag.5.value',Tag5value)

	def get_DBInstanceType(self):
		return self.get_query_params().get('DBInstanceType')

	def set_DBInstanceType(self,DBInstanceType):
		self.add_query_param('DBInstanceType',DBInstanceType)

	def get_Tags(self):
		return self.get_query_params().get('Tags')

	def set_Tags(self,Tags):
		self.add_query_param('Tags',Tags)

	def get_VSwitchId(self):
		return self.get_query_params().get('VSwitchId')

	def set_VSwitchId(self,VSwitchId):
		self.add_query_param('VSwitchId',VSwitchId)

	def get_Tag1key(self):
		return self.get_query_params().get('Tag.1.key')

	def set_Tag1key(self,Tag1key):
		self.add_query_param('Tag.1.key',Tag1key)

	def get_VpcId(self):
		return self.get_query_params().get('VpcId')

	def set_VpcId(self,VpcId):
		self.add_query_param('VpcId',VpcId)

	def get_Tag2value(self):
		return self.get_query_params().get('Tag.2.value')

	def set_Tag2value(self,Tag2value):
		self.add_query_param('Tag.2.value',Tag2value)

	def get_Tag4key(self):
		return self.get_query_params().get('Tag.4.key')

	def set_Tag4key(self,Tag4key):
		self.add_query_param('Tag.4.key',Tag4key)

	def get_InstanceNetworkType(self):
		return self.get_query_params().get('InstanceNetworkType')

	def set_InstanceNetworkType(self,InstanceNetworkType):
		self.add_query_param('InstanceNetworkType',InstanceNetworkType)