import subprocess

from django.db.backends.base.client import BaseDatabaseClient

class DatabaseClient(BaseDatabaseClient):
    executable_name = 'disql'

    def runshell(self, parameters):                        
        args = [self.executable_name, self.connection._connect_string()]        

        subprocess.call(args)

