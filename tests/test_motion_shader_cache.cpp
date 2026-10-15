// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
// Test template: the runner inserts the actual emitter and MotionVectors declaration.
#include "common/types.h"
#include "shader_recompiler/motion_address.h"
#include <sirit/sirit.h>
#include <vulkan/vulkan.h>
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace Shader {
@MOTION_DECLARATION@
namespace Backend::SPIRV {
using Sirit::Id;
struct PushData {static constexpr u32 MotionParamIndex=0;};
struct EmitContext:Sirit::Module {
    EmitContext():Module{0x00010300}{}
    std::array<Id,5> U32{},F32{},U1{};
    Id U64{},output_position{},push_data_block{},vertex_index{},instance_id{},motion_out_cur{},motion_out_prev{},u32_zero_value{};
    Id ConstU32(u32 value){return Constant(U32[1],value);}
};
@MOTION_EMITTER@

std::vector<u32> Emit(u64 params,u64 positions) {
    MotionVectors::params_address=params;MotionVectors::positions_address=positions;
    EmitContext ctx;
    ctx.AddCapability(spv::Capability::Shader);ctx.AddCapability(spv::Capability::Int64);
    ctx.AddCapability(spv::Capability::PhysicalStorageBufferAddresses);
    ctx.AddExtension("SPV_KHR_physical_storage_buffer");
    ctx.SetMemoryModel(spv::AddressingModel::PhysicalStorageBuffer64,spv::MemoryModel::GLSL450);
    ctx.U32[1]=ctx.TypeInt(32,false);ctx.U32[4]=ctx.TypeVector(ctx.U32[1],4);
    ctx.U1[1]=ctx.TypeBool();ctx.F32[1]=ctx.TypeFloat(32);ctx.F32[4]=ctx.TypeVector(ctx.F32[1],4);
    ctx.U64=ctx.TypeInt(64,false);ctx.u32_zero_value=ctx.ConstU32(0);
    const auto input=ctx.TypePointer(spv::StorageClass::Input,ctx.U32[1]);
    const auto output=ctx.TypePointer(spv::StorageClass::Output,ctx.F32[4]);
    ctx.vertex_index=ctx.AddGlobalVariable(input,spv::StorageClass::Input);
    ctx.instance_id=ctx.AddGlobalVariable(input,spv::StorageClass::Input);
    ctx.Decorate(ctx.vertex_index,spv::Decoration::BuiltIn,spv::BuiltIn::VertexIndex);
    ctx.Decorate(ctx.instance_id,spv::Decoration::BuiltIn,spv::BuiltIn::InstanceIndex);
    ctx.output_position=ctx.AddGlobalVariable(output,spv::StorageClass::Output);
    ctx.motion_out_cur=ctx.AddGlobalVariable(output,spv::StorageClass::Output);
    ctx.motion_out_prev=ctx.AddGlobalVariable(output,spv::StorageClass::Output);
    ctx.Decorate(ctx.output_position,spv::Decoration::BuiltIn,spv::BuiltIn::Position);
    ctx.Decorate(ctx.motion_out_cur,spv::Decoration::Location,30u);
    ctx.Decorate(ctx.motion_out_prev,spv::Decoration::Location,31u);
    const auto push=ctx.TypeStruct(ctx.U32[1]);
    ctx.Decorate(push,spv::Decoration::Block);ctx.MemberDecorate(push,0u,spv::Decoration::Offset,0u);
    ctx.push_data_block=ctx.AddGlobalVariable(ctx.TypePointer(spv::StorageClass::PushConstant,push),spv::StorageClass::PushConstant);
    const auto type=ctx.TypeVoid();const auto main=ctx.OpFunction(type,spv::FunctionControlMask::MaskNone,ctx.TypeFunction(type));
    ctx.AddLabel();
    const auto zero=ctx.Constant(ctx.F32[1],0.0f),one=ctx.Constant(ctx.F32[1],1.0f);
    ctx.OpStore(ctx.output_position,ctx.ConstantComposite(ctx.F32[4],zero,zero,zero,one));
    EmitVertexMotion(ctx);ctx.OpReturn();ctx.OpFunctionEnd();
    ctx.AddEntryPoint(spv::ExecutionModel::Vertex,main,"main",ctx.vertex_index,ctx.instance_id,
                     ctx.output_position,ctx.motion_out_cur,ctx.motion_out_prev);
    return ctx.Assemble();
}
}
}

void Check(VkResult result){if(result!=VK_SUCCESS)throw std::runtime_error("Vulkan result "+std::to_string(result));}
struct Device {
    VkInstance instance{};VkPhysicalDevice physical{};VkDevice device{};VkQueue queue{};
    VkCommandPool pool{};VkRenderPass pass{};VkFramebuffer framebuffer{};VkPipelineLayout layout{};
    Device(){
        VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};app.pApplicationName="R42 motion cache execution";app.apiVersion=VK_API_VERSION_1_2;
        VkInstanceCreateInfo create{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};create.pApplicationInfo=&app;
        Check(vkCreateInstance(&create,nullptr,&instance));
        u32 count{};Check(vkEnumeratePhysicalDevices(instance,&count,nullptr));assert(count);
        std::vector<VkPhysicalDevice> devices(count);Check(vkEnumeratePhysicalDevices(instance,&count,devices.data()));physical=devices.front();
        VkPhysicalDeviceProperties properties{};vkGetPhysicalDeviceProperties(physical,&properties);
        std::printf("Vulkan execution device: %s\n",properties.deviceName);
        u32 family_count{};vkGetPhysicalDeviceQueueFamilyProperties(physical,&family_count,nullptr);
        std::vector<VkQueueFamilyProperties> families(family_count);vkGetPhysicalDeviceQueueFamilyProperties(physical,&family_count,families.data());
        u32 family=0;while(family<family_count && !(families[family].queueFlags&VK_QUEUE_GRAPHICS_BIT))++family;assert(family<family_count);
        VkPhysicalDeviceBufferDeviceAddressFeatures bda{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_BUFFER_DEVICE_ADDRESS_FEATURES};
        VkPhysicalDeviceFeatures2 features{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};features.pNext=&bda;vkGetPhysicalDeviceFeatures2(physical,&features);
        assert(bda.bufferDeviceAddress && features.features.shaderInt64 && features.features.vertexPipelineStoresAndAtomics);
        VkPhysicalDeviceFeatures enabled{};enabled.shaderInt64=enabled.vertexPipelineStoresAndAtomics=VK_TRUE;
        const float priority=1;VkDeviceQueueCreateInfo q{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};q.queueFamilyIndex=family;q.queueCount=1;q.pQueuePriorities=&priority;
        bda.bufferDeviceAddress=VK_TRUE;bda.bufferDeviceAddressCaptureReplay=bda.bufferDeviceAddressMultiDevice=VK_FALSE;
        VkDeviceCreateInfo d{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};d.pNext=&bda;d.queueCreateInfoCount=1;d.pQueueCreateInfos=&q;d.pEnabledFeatures=&enabled;
        Check(vkCreateDevice(physical,&d,nullptr,&device));vkGetDeviceQueue(device,family,0,&queue);
        VkCommandPoolCreateInfo pc{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};pc.queueFamilyIndex=family;pc.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;Check(vkCreateCommandPool(device,&pc,nullptr,&pool));
        VkSubpassDescription sub{};sub.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS;
        VkRenderPassCreateInfo rp{VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO};rp.subpassCount=1;rp.pSubpasses=&sub;Check(vkCreateRenderPass(device,&rp,nullptr,&pass));
        VkFramebufferCreateInfo fb{VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO};fb.renderPass=pass;fb.width=fb.height=fb.layers=1;Check(vkCreateFramebuffer(device,&fb,nullptr,&framebuffer));
        const VkPushConstantRange push{VK_SHADER_STAGE_VERTEX_BIT,0,4};VkPipelineLayoutCreateInfo pl{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};pl.pushConstantRangeCount=1;pl.pPushConstantRanges=&push;Check(vkCreatePipelineLayout(device,&pl,nullptr,&layout));
    }
    ~Device(){if(device){vkDeviceWaitIdle(device);vkDestroyPipelineLayout(device,layout,nullptr);vkDestroyFramebuffer(device,framebuffer,nullptr);vkDestroyRenderPass(device,pass,nullptr);vkDestroyCommandPool(device,pool,nullptr);vkDestroyDevice(device,nullptr);}if(instance)vkDestroyInstance(instance,nullptr);}
    void Draw(std::span<const u32> code){
        VkShaderModuleCreateInfo sm{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};sm.codeSize=code.size_bytes();sm.pCode=code.data();VkShaderModule module{};Check(vkCreateShaderModule(device,&sm,nullptr,&module));
        VkPipelineShaderStageCreateInfo stage{VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO};stage.stage=VK_SHADER_STAGE_VERTEX_BIT;stage.module=module;stage.pName="main";
        VkPipelineVertexInputStateCreateInfo vi{VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
        VkPipelineInputAssemblyStateCreateInfo ia{VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO};ia.topology=VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
        const VkViewport viewport{0,0,1,1,0,1};const VkRect2D rect{{0,0},{1,1}};VkPipelineViewportStateCreateInfo vp{VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO};vp.viewportCount=vp.scissorCount=1;vp.pViewports=&viewport;vp.pScissors=&rect;
        VkPipelineRasterizationStateCreateInfo raster{VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO};raster.rasterizerDiscardEnable=VK_TRUE;raster.lineWidth=1;raster.polygonMode=VK_POLYGON_MODE_FILL;
        VkPipelineMultisampleStateCreateInfo ms{VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO};ms.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT;
        VkGraphicsPipelineCreateInfo pi{VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO};pi.stageCount=1;pi.pStages=&stage;pi.pVertexInputState=&vi;pi.pInputAssemblyState=&ia;pi.pViewportState=&vp;pi.pRasterizationState=&raster;pi.pMultisampleState=&ms;pi.layout=layout;pi.renderPass=pass;
        VkPipeline pipeline{};Check(vkCreateGraphicsPipelines(device,VK_NULL_HANDLE,1,&pi,nullptr,&pipeline));
        VkCommandBufferAllocateInfo ca{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};ca.commandPool=pool;ca.commandBufferCount=1;ca.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;VkCommandBuffer command{};Check(vkAllocateCommandBuffers(device,&ca,&command));
        VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};Check(vkBeginCommandBuffer(command,&begin));
        VkRenderPassBeginInfo start{VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO};start.renderPass=pass;start.framebuffer=framebuffer;start.renderArea.extent={1,1};vkCmdBeginRenderPass(command,&start,VK_SUBPASS_CONTENTS_INLINE);
        vkCmdBindPipeline(command,VK_PIPELINE_BIND_POINT_GRAPHICS,pipeline);const u32 index=0;vkCmdPushConstants(command,layout,VK_SHADER_STAGE_VERTEX_BIT,0,4,&index);vkCmdDraw(command,3,1,0,0);vkCmdEndRenderPass(command);
        VkMemoryBarrier memory{VK_STRUCTURE_TYPE_MEMORY_BARRIER};memory.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT;memory.dstAccessMask=VK_ACCESS_HOST_READ_BIT;vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_VERTEX_SHADER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&memory,0,nullptr,0,nullptr);
        Check(vkEndCommandBuffer(command));VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.commandBufferCount=1;submit.pCommandBuffers=&command;Check(vkQueueSubmit(queue,1,&submit,VK_NULL_HANDLE));Check(vkQueueWaitIdle(queue));
        vkFreeCommandBuffers(device,pool,1,&command);vkDestroyPipeline(device,pipeline,nullptr);vkDestroyShaderModule(device,module,nullptr);
    }
};
struct Buffer {
    Device& gpu;VkBuffer buffer{};VkDeviceMemory memory{};void* mapped{};u64 address{};
    explicit Buffer(Device& device,size_t size):gpu{device}{
        VkBufferCreateInfo create{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};create.size=size;create.usage=VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT|VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;Check(vkCreateBuffer(gpu.device,&create,nullptr,&buffer));
        VkMemoryRequirements requirements{};vkGetBufferMemoryRequirements(gpu.device,buffer,&requirements);VkPhysicalDeviceMemoryProperties types{};vkGetPhysicalDeviceMemoryProperties(gpu.physical,&types);
        u32 type=0;const auto flags=VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
        while(type<types.memoryTypeCount && (!(requirements.memoryTypeBits&(1u<<type)) || (types.memoryTypes[type].propertyFlags&flags)!=flags))++type;assert(type<types.memoryTypeCount);
        VkMemoryAllocateFlagsInfo af{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_FLAGS_INFO};af.flags=VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT;
        VkMemoryAllocateInfo ai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ai.pNext=&af;ai.allocationSize=requirements.size;ai.memoryTypeIndex=type;Check(vkAllocateMemory(gpu.device,&ai,nullptr,&memory));Check(vkBindBufferMemory(gpu.device,buffer,memory,0));Check(vkMapMemory(gpu.device,memory,0,VK_WHOLE_SIZE,0,&mapped));
        VkBufferDeviceAddressInfo info{VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO};info.buffer=buffer;address=vkGetBufferDeviceAddress(gpu.device,&info);assert(address);
    }
    ~Buffer(){vkUnmapMemory(gpu.device,memory);vkDestroyBuffer(gpu.device,buffer,nullptr);vkFreeMemory(gpu.device,memory,nullptr);}
};
void Write(const std::filesystem::path& path,const std::vector<u32>& code){std::ofstream out(path,std::ios::binary);out.write(reinterpret_cast<const char*>(code.data()),code.size()*4);assert(out);}
int main(int argc,char**argv){
    assert(argc>=2);const std::filesystem::path folder{argv[1]};
    using Shader::Backend::SPIRV::Emit;namespace Motion=Shader::MotionAddress;
    const auto first=Emit(0x100000000ull,0x200000000ull),second=Emit(0x300000000ull,0x400000000ull);
#if !CURRENT
    assert(first!=second);std::puts("R41 CONTROL: actual vertex-motion emission changes with process-local addresses; previous-run modules cannot be reused.");
#else
    assert(first==second);const auto cached=first;
    Motion::params_address=0x500000000ull;Motion::positions_address=0x600000000ull;
    std::vector<u32> linked;assert(Motion::Link(cached,linked)==Motion::Result::Linked && linked!=cached && cached==first);
    Write(folder/"portable.spv",cached);Write(folder/"linked.spv",linked);
    Motion::params_address=0;assert(Motion::Link(cached,linked)==Motion::Result::Invalid);
    auto malformed=cached;malformed.back()=0;assert(Motion::Link(malformed,linked)==Motion::Result::Invalid);
    std::puts("PASS: actual vertex-motion emission is byte-identical across allocations; linking leaves cached code unchanged and rejects unavailable buffers/malformed instructions.");
    if(argc>2 && std::string{argv[2]}=="--vulkan"){
        Device gpu;Buffer params_a{gpu,32},positions_a{gpu,64},params_b{gpu,32},positions_b{gpu,64};
        assert(params_a.address!=params_b.address && positions_a.address!=positions_b.address);
        const auto prepare=[](Buffer& params,Buffer& positions,u32 vertices,u32 first_vertex){
            const std::array<u32,8> p{1,0,vertices,1,first_vertex,0,1,0};std::memcpy(params.mapped,p.data(),32);std::fill_n(static_cast<float*>(positions.mapped),16,-7.f);
        };
        prepare(params_a,positions_a,3,0);Motion::params_address=params_a.address;Motion::positions_address=positions_a.address;
        assert(Motion::Link(cached,linked)==Motion::Result::Linked);gpu.Draw(linked);
        const auto check=[](Buffer& positions,unsigned stored){const auto* p=static_cast<float*>(positions.mapped);for(unsigned i=0;i<4;++i)for(unsigned j=0;j<4;++j)assert(p[i*4+j]==(i>0 && i<=stored ? j==3?1.f:0.f : -7.f));};
        check(positions_a,3);
        std::fill_n(static_cast<float*>(positions_a.mapped),16,99.f);prepare(params_b,positions_b,2,1);
        Motion::params_address=params_b.address;Motion::positions_address=positions_b.address;
        assert(Motion::Link(cached,linked)==Motion::Result::Linked);gpu.Draw(linked);check(positions_b,2);
        for(unsigned i=0;i<16;++i)assert(static_cast<float*>(positions_a.mapped)[i]==99.f);
        assert(cached==first);
        std::puts("PASS: the same cached production vertex-motion shader writes the current session's buffers across two distinct Vulkan allocations; old buffers remain untouched and current parameter bounds are respected.");
    }
#endif
}
