"""Execute the production readback selector: old Off/invalid settings migrate safely."""
from pathlib import Path
import os,subprocess,tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'gpu/shim/core/emulator_settings.h').read_text()
a=s.index('    u32 GetReadbacksMode()');b=s.index('{',a)+1;depth=1
while depth:depth+=(s[b]=='{')-(s[b]=='}');b+=1
cpp='''#include <cassert>
#include <cstdlib>
#include <cstdint>
using u32=uint32_t;
enum GpuReadbacksMode {Disabled=0,Relaxed=1,Precise=2};
struct Settings {
 static long Number(const char* name,long fallback){const char* p=std::getenv(name);return p?std::strtol(p,nullptr,10):fallback;}
@METHOD@
};
int main(int argc,char** argv){assert(argc==2);Settings s;assert(s.GetReadbacksMode()==u32(std::atoi(argv[1])));}
'''.replace('@METHOD@',s[a:b])
with tempfile.TemporaryDirectory(prefix='readback-policy-') as temporary:
 p=Path(temporary)/'test.cpp';p.write_text(cpp);exe=p.with_suffix('')
 subprocess.run([os.environ.get('CXX','g++'),'-std=c++20',str(p),'-o',str(exe)],check=True)
 for value,expected in [(None,1),('0',1),('1',1),('2',2),('-1',1),('9',1)]:
  env=dict(os.environ);env.pop('BB_READBACKS',None)
  if value is not None:env['BB_READBACKS']=value
  subprocess.run([str(exe),str(expected)],env=env,check=True)
print('PASS: production default/Off/Relaxed/Precise/invalid readback settings preserve required GPU readbacks.')
