#!/usr/bin/env python

from setuptools import setup
import distutils.dist
import distutils.command
import os
import sys
try:
    import distutils.command.bdist_msi
except ImportError:
    distutils.command.bdist_msi = None
try:
    import distutils.command.bdist_wininst
except ImportError:
    distutils.command.bdist_wininst = None
import distutils.command.bdist_rpm

# define build constants
dm_version = os.environ.get("DM_VER")

if dm_version is not None:
    DAMENG_VERSION = dm_version
else:
    DAMENG_VERSION = "7.1"

# tweak distribution full name to include the Dameng version
class Distribution(distutils.dist.Distribution):

    def get_fullname_with_dameng_version(self):
        name = self.metadata.get_fullname()
        return "%s-DM%s" % (name, DAMENG_VERSION)
    
# tweak the RPM build command to include the Python and Dameng version
class bdist_rpm(distutils.command.bdist_rpm.bdist_rpm):

    def run(self):
        distutils.command.bdist_rpm.bdist_rpm.run(self)
        specFile = os.path.join(self.rpm_base, "SPECS",
                "%s.spec" % self.distribution.get_name())
        queryFormat = "%{name}-%{version}-%{release}.%{arch}.rpm"
        command = "rpm -q --qf '%s' --specfile %s" % (queryFormat, specFile)        
        origFileName = os.popen(command).read()        
        names = origFileName.split("rpm")
        for origFileName in names:
            if len(origFileName) > 0:
                origFileName += "rpm"
                parts = origFileName.split("-")
                parts.insert(2, DAMENG_VERSION)
                parts.insert(3, "py%s%s" % sys.version_info[:2])
                newFileName = "-".join(parts)                
                self.move_file(os.path.join("dist", origFileName), os.path.join("dist", newFileName))               

commandClasses = dict(bdist_rpm = bdist_rpm)

# tweak the Windows installer names to include the Dameng version
if distutils.command.bdist_msi is not None:

    class bdist_msi(distutils.command.bdist_msi.bdist_msi):

        def run(self):
            origMethod = self.distribution.get_fullname
            self.distribution.get_fullname = \
                    self.distribution.get_fullname_with_dameng_version
            distutils.command.bdist_msi.bdist_msi.run(self)
            self.distribution.get_fullname = origMethod

    commandClasses["bdist_msi"] = bdist_msi

if distutils.command.bdist_wininst is not None:

    class bdist_wininst(distutils.command.bdist_wininst.bdist_wininst):

        def run(self):
            origMethod = self.distribution.get_fullname
            self.distribution.get_fullname = \
                    self.distribution.get_fullname_with_dameng_version
            distutils.command.bdist_wininst.bdist_wininst.run(self)
            self.distribution.get_fullname = origMethod

    commandClasses["bdist_wininst"] = bdist_wininst

setup(name='dmDjango',
      version='2.0.3',
      distclass = Distribution,
      description='Dameng database backend for Django',
      cmdclass = commandClasses,
      author='Dameng',
      author_email='',
      url='',
      packages=['dmDjango'],
      package_dir={'dmDjango': 'src'},
      zip_safe=False,
      )
