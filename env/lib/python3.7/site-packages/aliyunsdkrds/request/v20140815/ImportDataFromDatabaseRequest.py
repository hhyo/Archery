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
class ImportDataFromDatabaseRequest(RpcRequest):

	def __init__(self):
		RpcRequest.__init__(self, 'Rds', '2014-08-15', 'ImportDataFromDatabase','rds')

	def get_ResourceOwnerId(self):
		return self.get_query_params().get('ResourceOwnerId')

	def set_ResourceOwnerId(self,ResourceOwnerId):
		self.add_query_param('ResourceOwnerId',ResourceOwnerId)

	def get_ImportDataType(self):
		return self.get_query_params().get('ImportDataType')

	def set_ImportDataType(self,ImportDataType):
		self.add_query_param('ImportDataType',ImportDataType)

	def get_ResourceOwnerAccount(self):
		return self.get_query_params().get('ResourceOwnerAccount')

	def set_ResourceOwnerAccount(self,ResourceOwnerAccount):
		self.add_query_param('ResourceOwnerAccount',ResourceOwnerAccount)

	def get_IsLockTable(self):
		return self.get_query_params().get('IsLockTable')

	def set_IsLockTable(self,IsLockTable):
		self.add_query_param('IsLockTable',IsLockTable)

	def get_OwnerAccount(self):
		return self.get_query_params().get('OwnerAccount')

	def set_OwnerAccount(self,OwnerAccount):
		self.add_query_param('OwnerAccount',OwnerAccount)

	def get_SourceDatabaseDBNames(self):
		return self.get_query_params().get('SourceDatabaseDBNames')

	def set_SourceDatabaseDBNames(self,SourceDatabaseDBNames):
		self.add_query_param('SourceDatabaseDBNames',SourceDatabaseDBNames)

	def get_SourceDatabaseIp(self):
		return self.get_query_params().get('SourceDatabaseIp')

	def set_SourceDatabaseIp(self,SourceDatabaseIp):
		self.add_query_param('SourceDatabaseIp',SourceDatabaseIp)

	def get_OwnerId(self):
		return self.get_query_params().get('OwnerId')

	def set_OwnerId(self,OwnerId):
		self.add_query_param('OwnerId',OwnerId)

	def get_SourceDatabasePassword(self):
		return self.get_query_params().get('SourceDatabasePassword')

	def set_SourceDatabasePassword(self,SourceDatabasePassword):
		self.add_query_param('SourceDatabasePassword',SourceDatabasePassword)

	def get_SourceDatabasePort(self):
		return self.get_query_params().get('SourceDatabasePort')

	def set_SourceDatabasePort(self,SourceDatabasePort):
		self.add_query_param('SourceDatabasePort',SourceDatabasePort)

	def get_SourceDatabaseUserName(self):
		return self.get_query_params().get('SourceDatabaseUserName')

	def set_SourceDatabaseUserName(self,SourceDatabaseUserName):
		self.add_query_param('SourceDatabaseUserName',SourceDatabaseUserName)

	def get_DBInstanceId(self):
		return self.get_query_params().get('DBInstanceId')

	def set_DBInstanceId(self,DBInstanceId):
		self.add_query_param('DBInstanceId',DBInstanceId)