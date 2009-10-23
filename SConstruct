from tools import *

# We need scons 0.98 or later
EnsureSConsVersion(0, 98)

# Set up build environment:
vars = Variables('config.py', ARGUMENTS)
add_common_variables(vars, "saliweb")
env = MyEnvironment(variables=vars, require_modeller=False,
                    tools=["default", "sphinx"], toolpath=["tools"])
Help(vars.GenerateHelpText(env))

# Make these objects available to SConscript files:
Export('env')

# Subdirectories to build:
test = SConscript('test/SConscript')
SConscript('perl/saliweb/SConscript')
SConscript('python/saliweb/SConscript')
SConscript('bin/SConscript')
SConscript('doc/SConscript')
SConscript('web/SConscript')

# Run test cases by default:
env.Default(test)
