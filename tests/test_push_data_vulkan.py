"""Execute the production push layout with a real Vulkan compute queue (software permitted)."""
from pathlib import Path
import runpy, subprocess
m=runpy.run_path(str(Path(__file__).with_name('test_push_data_layout.py')))
root=m['ROOT'];out=m['OUT'];template=m['TEMPLATE']
a=template.index(' auto out=c.AddGlobalVariable(');b=template.index(' const auto t=c.TypeVoid();',a)
template=template[:a]+''' auto block=c.TypeStruct(c.U32[1]);c.Decorate(block,spv::Decoration::Block);c.MemberDecorate(block,0u,spv::Decoration::Offset,0u);
 auto out=c.AddGlobalVariable(c.TypePointer(spv::StorageClass::StorageBuffer,block),spv::StorageClass::StorageBuffer);
 c.Decorate(out,spv::Decoration::DescriptorSet,0u);c.Decorate(out,spv::Decoration::Binding,0u);
'''+template[b:]
template=template.replace('c.OpStore(out,sum);','auto dst=c.OpAccessChain(c.TypePointer(spv::StorageClass::StorageBuffer,c.U32[1]),out,c.ConstU32(0));c.OpStore(dst,sum);').replace('c.AddEntryPoint(spv::ExecutionModel::Fragment,main,"main",out);','c.AddEntryPoint(spv::ExecutionModel::GLCompute,main,"main");').replace('c.AddExecutionMode(main,spv::ExecutionMode::OriginUpperLeft);','c.AddExecutionMode(main,spv::ExecutionMode::LocalSize,1u,1u,1u);')
for name,old in [('r52-compute',True),('current-compute',False)]:
 decl=m['extract'](m['read']('gpu/shadps4/shader_recompiler/resource.h',old),'struct PushData {','static_assert(sizeof(PushData)')
 define=m['extract'](m['read']('gpu/shadps4/shader_recompiler/backend/spirv/spirv_emit_context.cpp',old),'void EmitContext::DefinePushDataBlock()','EmitContext::BufferSpv')
 cpp=out/(name+'.cpp');exe=out/name;cpp.write_text(template.replace('@PUSH@',decl).replace('@DEFINE@',define))
 subprocess.run(['g++','-std=c++20','-O1',*m['INCLUDES'],str(cpp),*map(str,m['objects']),'-o',str(exe)],check=True)
 subprocess.run([str(exe),str(out/(name+'.spv')),str(out/(name+'-upgraded.spv'))],check=True)
for name in ['current-compute','r52-compute-upgraded']:subprocess.run([str(m['validator']),'--target-env','vulkan1.2',str(out/(name+'.spv'))],check=True)
runner=out/'vulkan-execution';subprocess.run(['g++','-std=c++20','-O1','-I'+str(root/'out/test-headers'),str(root/'tests/test_push_data_vulkan.cpp'),'-Wl,-l:libvulkan.so.1','-o',str(runner)],check=True)
subprocess.run([str(runner),str(out/'current-compute.spv'),str(out/'r52-compute-upgraded.spv')],check=True,timeout=60)
