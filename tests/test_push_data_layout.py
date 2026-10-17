"""Validate actual old/current push declarations and migration at the SPIR-V boundary."""
from pathlib import Path
import subprocess,sys,concurrent.futures
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/verification/push-layout53';OUT.mkdir(parents=True,exist_ok=True)
SIRIT=ROOT/'gpu/third_party/sirit'
INCLUDES=['-I'+str(ROOT/'gpu/shadps4'),'-I'+str(SIRIT/'include'),'-I'+str(SIRIT/'externals/SPIRV-Headers/include'),'-I'+str(SIRIT/'src')]
def compile_obj(p):
 o=OUT/(p.stem+'.o')
 if not o.exists():subprocess.run(['g++','-std=c++20','-O1',*INCLUDES,'-c',str(p),'-o',str(o)],check=True)
 return o
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:objects=list(pool.map(compile_obj,sorted((SIRIT/'src').rglob('*.cpp'))))
def read(p,old):return subprocess.check_output(['git','show','872a14f4d990fa7dcb0d606484a83faa619cc75f:'+p],cwd=ROOT,text=True) if old else (ROOT/p).read_text()
def extract(s,a,b):return s[s.index(a):s.index(b,s.index(a))]
TEMPLATE=r'''
#include <sirit/sirit.h>
#include "shader_recompiler/push_data_upgrade.h"
#include <array>
#include <cassert>
#include <fstream>
#include <string>
#include <algorithm>
using u32=uint32_t;using u8=uint8_t;using Sirit::Id;
constexpr u32 NUM_BUFFERS=56;
#define ASSERT(x) assert(x)
@PUSH@
struct EmitContext: Sirit::Module {
 std::array<Id,5> U32{},F32{};Id push_data_block;std::vector<Id> interfaces;
 EmitContext():Module(0x00010300){}
 Id ConstU32(u32 v){return Constant(U32[1],v);}
 Id DefineVar(Id t,spv::StorageClass c){return AddGlobalVariable(TypePointer(c,t),c);}
 void DefinePushDataBlock();
};
@DEFINE@
void save(const char* path,std::span<const u32> code){std::ofstream f(path,std::ios::binary);f.write((const char*)code.data(),code.size_bytes());}
int main(int argc,char** argv){
 assert(argc==3);EmitContext c;c.AddCapability(spv::Capability::Shader);
 c.SetMemoryModel(spv::AddressingModel::Logical,spv::MemoryModel::GLSL450);
 c.U32[1]=c.TypeInt(32,false);c.F32[1]=c.TypeFloat(32);
 for(int i=2;i<5;++i){c.U32[i]=c.TypeVector(c.U32[1],i);c.F32[i]=c.TypeVector(c.F32[1],i);}
 c.DefinePushDataBlock();
 auto out=c.AddGlobalVariable(c.TypePointer(spv::StorageClass::Output,c.U32[1]),spv::StorageClass::Output);
 c.Decorate(out,spv::Decoration::Location,0u);
 const auto t=c.TypeVoid();auto main=c.OpFunction(t,spv::FunctionControlMask::MaskNone,c.TypeFunction(t));c.AddLabel();
 auto sum=c.ConstU32(0);const auto ptr=c.TypePointer(spv::StorageClass::PushConstant,c.U32[1]);
 for(u32 i=0;i<56;++i){auto address=c.OpAccessChain(ptr,c.push_data_block,c.ConstU32(4+i/16),c.ConstU32((i%16)/4));sum=c.OpIAdd(c.U32[1],sum,c.OpLoad(c.U32[1],address));}
 for(u32 i:{PushData::MotionParamIndex,PushData::SceneSizeIndex}){auto address=c.OpAccessChain(ptr,c.push_data_block,c.ConstU32(i));sum=c.OpIAdd(c.U32[1],sum,c.OpLoad(c.U32[1],address));}
 c.OpStore(out,sum);c.OpReturn();c.OpFunctionEnd();c.AddEntryPoint(spv::ExecutionModel::Fragment,main,"main",out);
 c.AddExecutionMode(main,spv::ExecutionMode::OriginUpperLeft);
 auto code=c.Assemble();save(argv[1],code);std::vector<u32> upgraded;assert(Shader::PushLayout::Upgrade(code,upgraded));
 if(upgraded.empty())upgraded=code;save(argv[2],upgraded);
 std::vector<u32> again;assert(Shader::PushLayout::Upgrade(upgraded,again));assert(again.empty());
 const std::array<u32,6> malformed{0x07230203u,0x00010300u,0,2,0,0};assert(!Shader::PushLayout::Upgrade(malformed,again));
}
'''
for name,old in [('r52',True),('current',False)]:
 decl=extract(read('gpu/shadps4/shader_recompiler/resource.h',old),'struct PushData {','static_assert(sizeof(PushData)')
 define=extract(read('gpu/shadps4/shader_recompiler/backend/spirv/spirv_emit_context.cpp',old),'void EmitContext::DefinePushDataBlock()','EmitContext::BufferSpv')
 cpp=OUT/(name+'.cpp');cpp.write_text(TEMPLATE.replace('@PUSH@',decl).replace('@DEFINE@',define));exe=OUT/name
 subprocess.run(['g++','-std=c++20','-O1',*INCLUDES,str(cpp),*map(str,objects),'-o',str(exe)],check=True)
 subprocess.run([str(exe),str(OUT/(name+'.spv')),str(OUT/(name+'-upgraded.spv'))],check=True)
validator=ROOT.parent/'windows-build/host/usr/bin/spirv-val'
old=subprocess.run([str(validator),'--target-env','vulkan1.2',str(OUT/'r52.spv')],capture_output=True,text=True)
assert old.returncode!=0 and 'OpAccessChain' in old.stderr,old.stderr
print('R52 control rejected:',old.stderr.strip())
for name in ['current','current-upgraded','r52-upgraded']:subprocess.run([str(validator),'--target-env','vulkan1.2',str(OUT/(name+'.spv'))],check=True)
print('PASS: actual R52 declaration fails on buffer 40+, current and cache migration validate all 56 buffer accesses plus motion/scene; migration idempotent.')
