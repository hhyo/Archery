"""Distutils script for dmPython.

    python setup.py build install

"""
import sys
if sys.version_info[:2] < (3, 12):
    import distutils.command
    try:
        import distutils.command.bdist_msi
    except ImportError:
        distutils.command.bdist_msi = None
    try:
        import distutils.command.bdist_wininst
    except ImportError:
        distutils.command.bdist_wininst = None
    import distutils.command.bdist_rpm
    import distutils.command.build
    import distutils.core
    import distutils.dist
    import distutils.util
import os
import re
import struct

if sys.version_info[:2] < (3, 12):
    from distutils.errors import DistutilsSetupError as SetupError
else:
    from setuptools.errors import SetupError

# if setuptools is detected, use it to add support for eggs
if sys.version_info[:2] < (3, 12):
    try:
        from setuptools import setup, Extension
    except:
        from distutils.core import setup
        from distutils.extension import Extension
else:
    from setuptools import setup, Extension

# define build constants
BUILD_VERSION = "2.5.22"
dm_version = os.environ.get("DM_VER")

if dm_version is not None:
    DAMENG_VERSION = dm_version
else:
    DAMENG_VERSION = "8.1"

# method for checking a potential Dameng home
def CheckDmHome(directoryToCheck):
    global dmHome, dmLibDir

        
    if sys.platform in ("win32", "cygwin"):
        if sys.version_info[:2] > (3, 7):
            str_pthtemp=sys.executable[0:len(sys.executable)-len(sys.executable.split('\\')[-1])]+'Lib\\site-packages\\dmPython.pth'
            file=open(str_pthtemp,'w')
            write_pthstr='import dpi'
            file.write(write_pthstr)
            file.close()
        if struct.calcsize("P") == 4:
            subDirs = ["bin", "debug", "release", "dpi"]
        else:
            subDirs = ["bin", "x64/debug", "x64/release", "dpi"]
        filesToCheck = ["dmdpi.dll"]
    elif sys.platform == "darwin":
        subDirs = ["bin"]
        filesToCheck = ["libdmdpi"]
    else:
        subDirs = ["bin", "build/linux/linux_build/debug", "build/linux/linux_build/release", "dpi"]
        filesToCheck = ["libdmdpi.so"]
        
    for baseFileName in filesToCheck:
        fileName = os.path.join(directoryToCheck, baseFileName)
        if os.path.exists(fileName):
            if os.path.basename(directoryToCheck).lower() == "bin":
                dmHome = os.path.dirname(directoryToCheck)
            else:
                dmHome = directoryToCheck
            dmLibDir = directoryToCheck   
            if sys.platform in ("win32", "cygwin"):
                if sys.version_info[:2] > (3, 7):
                    str_pytemp=sys.executable[0:len(sys.executable)-len(sys.executable.split('\\')[-1])]+'Lib\\site-packages\\dpi.py'
                    file=open(str_pytemp,'w')
                    write_pystr='import os\nos.add_dll_directory(r\'' + dmLibDir + '\')'
                    file.write(write_pystr)
                    file.close()
            return True
            
        for subDir in subDirs:
            fileName = os.path.join(directoryToCheck, subDir, baseFileName)
            if os.path.exists(fileName):
                dmHome = directoryToCheck
                dmLibDir = os.path.join(directoryToCheck, subDir)
                if sys.platform in ("win32", "cygwin"):
                    if sys.version_info[:2] > (3, 7):
                        str_pytemp=sys.executable[0:len(sys.executable)-len(sys.executable.split('\\')[-1])]+'Lib\\site-packages\\dpi.py'
                        file=open(str_pytemp,'w')
                        write_pystr='import os\nos.add_dll_directory(r\'' + dmLibDir + '\')'
                        file.write(write_pystr)
                        file.close()
                return True

        for subDir in subDirs:        
            dirName = os.path.dirname(directoryToCheck)
            fileName = os.path.join(dirName, subDir, baseFileName)
            if os.path.exists(fileName):
                dmHome = dirName
                dmLibDir = os.path.join(dirName, subDir)
                if sys.platform in ("win32", "cygwin"):
                    if sys.version_info[:2] > (3, 7):
                        str_pytemp=sys.executable[0:len(sys.executable)-len(sys.executable.split('\\')[-1])]+'Lib\\site-packages\\dpi.py'
                        file=open(str_pytemp,'w')
                        write_pystr='import os\nos.add_dll_directory(r\'' + dmLibDir + '\')'
                        file.write(write_pystr)
                        file.close()
                return True
                
    dmHome = dmLibDir = None
    return False

# try to determine the Dameng home
userDmHome = os.environ.get("DM_HOME")
if userDmHome is not None:
    if not CheckDmHome(userDmHome):
        messageFormat = "Dameng home (%s) does not refer to an " \
                "DM%s installation or dmdpi library missing."
        raise SetupError(messageFormat % (userDmHome,DAMENG_VERSION))
else:
    for path in os.environ["PATH"].split(os.pathsep):
        if CheckDmHome(path):
            break
    if dmHome is None:
        raise SetupError("cannot locate an Dameng software " \
                "installation")

# define some variables
if sys.platform == "win32":
    libDirs = [dmLibDir, os.path.join(dmHome, "include")]
    
    possibleIncludeDirs = ["python/dmPython_C/dmPython", "include", "dpi/src/include", "drivers/python/dmPython", "dpi/include"]    
    includeDirs = []
    for dir1 in possibleIncludeDirs:    
        path = os.path.normpath(os.path.join(dmHome, dir1))
        if os.path.isdir(path):
            includeDirs.append(path)
            
    if not includeDirs:
        message = "cannot locate Dameng include files in %s" % dmHome
        raise SetupError(message)
    libs = ["dmdpi"]
else:
    libDirs = [dmLibDir]
    libs = ["dmdpi"]
    possibleIncludeDirs = ["python/dmPython_C/dmPython", "include", "dpi/src/include", "drivers/python/dmPython", "dpi/include"]    
    includeDirs = []
    for dir in possibleIncludeDirs:
        path = os.path.join(dmHome, dir)
        if os.path.isdir(path):
            includeDirs.append(path)    
    if not includeDirs:
        raise SetupError("cannot locate Dameng include files")

# setup extra link and compile args
extraCompileArgs = ["-DBUILD_VERSION=%s" % BUILD_VERSION]
extraLinkArgs = []

# extension Macros definition if on 64bit platform,add DM64,othersise use default [defineMacros].
defineMacros = []
if struct.calcsize("P") == 4:
    defineMacros = []
else:
    defineMacros = [('DM64', None),]
if sys.platform == "win32":
    defineMacros.append(('WIN32', None))
    defineMacros.append(('_CRT_SECURE_NO_WARNINGS', None))
   
#extension Macro TRACE if a dmPython_trace.log needed in current directory.
#defineMacros.append(('TRACE', None))
if sys.version_info[:2] < (3, 12):
    # tweak distribution full name to include the Dameng version
    class Distribution(distutils.dist.Distribution):

        def get_fullname_with_dameng_version(self):
            name = self.metadata.get_fullname()
            return "%s-%s" % (name, DAMENG_VERSION)

if sys.version_info[:2] < (3, 12):
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

if sys.version_info[:2] < (3, 12):
    # tweak the build directories to include the Dameng version
    class build(distutils.command.build.build):

        def finalize_options(self):
            import distutils.util
            import os
            import sys
            platSpecifier = ".%s-%s" % \
                    (distutils.util.get_platform(), sys.version[0:3])
            if self.build_platlib is None:
                self.build_platlib = os.path.join(self.build_base,
                        "lib%s" % platSpecifier)
            if self.build_temp is None:
                self.build_temp = os.path.join(self.build_base,
                        "temp%s" % platSpecifier)
            distutils.command.build.build.finalize_options(self)

    class test(distutils.core.Command):
        description = "run the test suite for the extension"
        user_options = []

        def finalize_options(self):
            pass

        def initialize_options(self):
            pass

        def run(self):
            self.run_command("build")
            buildCommand = self.distribution.get_command_obj("build")
            sys.path.insert(0, os.path.abspath("test"))
            sys.path.insert(0, os.path.abspath(buildCommand.build_lib))
            if sys.version_info[0] < 3:
                execfile(os.path.join("test", "test.py"))
            else:
                fileName = os.path.join("test", "test3k.py")
                exec(open(fileName).read())

    commandClasses = dict(build = build, bdist_rpm = bdist_rpm, test = test)

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

# define classifiers for the package index
classifiers = [
        "Development Status :: 1 - Mature",
        "Intended Audience :: Developers",
        "License :: DPI Approved :: Python Software Foundation License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: C",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Topic :: Database"
]

# setup the extension
extension = Extension(
        name = "dmPython",
        include_dirs = includeDirs,
        libraries = libs,
        library_dirs = libDirs,
        extra_compile_args = extraCompileArgs,
        extra_link_args = extraLinkArgs,
        sources = ['py_Dameng.c','row.c','Cursor.c','Connection.c','Environment.c','Error.c','Buffer.c',
                   'exLob.c','exObject.c','tObject.c', 'var.c','vCursor.c','vDateTime.c','vInterval.c','vLob.c','vNumber.c',
                   'vObject.c', 'vString.c', 'vlong.c', 'exBfile.c', 'vBfile.c','trc.c'],
        depends = [],        
        define_macros = defineMacros
        )
if sys.version_info[:2] < (3, 12):
    # perform the setup
    setup(
            name = "dmPython",
            version = BUILD_VERSION,
            distclass = Distribution,
            description = "Python interface to Dameng",        
            cmdclass = commandClasses,        
            long_description = \
                "Python interface to Dameng conforming to the Python DB API 2.0 "
                "specification.\n"
                "See http://www.python.org/topics/database/DatabaseAPI-2.0.html.",        
            ext_modules = [extension],
            keywords = "Dameng",
            license = "Python Software Foundation License",
            classifiers = classifiers)
else:
    setup(
            name = "dmPython",
            version = BUILD_VERSION,
            description = "Python interface to Dameng",              
            long_description = \
                "Python interface to Dameng conforming to the Python DB API 2.0 "
                "specification.\n"
                "See http://www.python.org/topics/database/DatabaseAPI-2.0.html.",        
            ext_modules = [extension],
            keywords = "Dameng",
            license = "Python Software Foundation License",
            classifiers = classifiers)
        
        
