// SPDX-License-Identifier: GPL-2.0-or-later
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// Runner inserts the production GLSL body and common native Vulkan fixture.
#define GLM_FORCE_SWIZZLE
#include <glm/glm.hpp>
#include <glm/common.hpp>
#include <glm/gtc/type_ptr.hpp>
#include <vulkan/vulkan.h>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <memory>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>
#include "camera.h"
using namespace glm;
using u32=uint32_t;using u64=uint64_t;
constexpr unsigned W=97,H=65,N=W*H;
struct Texture {std::array<vec4,N> pixels;};
Texture depth_tex,object_tex,motion_img;
uvec3 gl_GlobalInvocationID;
vec4 reproject[3],proj,prev_proj;
vec2 size(W,H),jitter,previous_jitter;
unsigned mode=0;
vec4 texelFetch(const Texture& t,ivec2 p,int){return t.pixels.at(p.y*W+p.x);}
void imageStore(Texture& t,ivec2 p,vec4 v){t.pixels.at(p.y*W+p.x)=v;}
@KERNEL@
@GPU_HELPERS@

struct Image {
    Device& gpu;VkImage image{};VkImageView view{};VkDeviceMemory memory{};
    Image(Device& d,VkFormat format):gpu{d}{
        VkImageCreateInfo c{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};c.imageType=VK_IMAGE_TYPE_2D;c.format=format;c.extent={W,H,1};c.mipLevels=c.arrayLayers=1;c.samples=VK_SAMPLE_COUNT_1_BIT;c.tiling=VK_IMAGE_TILING_OPTIMAL;c.usage=VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_STORAGE_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT;
        Check(vkCreateImage(gpu.device,&c,nullptr,&image));VkMemoryRequirements req{};vkGetImageMemoryRequirements(gpu.device,image,&req);
        unsigned type=0;while(!(req.memoryTypeBits&(1u<<type)))++type;
        VkMemoryAllocateInfo a{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};a.allocationSize=req.size;a.memoryTypeIndex=type;Check(vkAllocateMemory(gpu.device,&a,nullptr,&memory));Check(vkBindImageMemory(gpu.device,image,memory,0));
        VkImageViewCreateInfo v{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};v.image=image;v.viewType=VK_IMAGE_VIEW_TYPE_2D;v.format=format;v.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};Check(vkCreateImageView(gpu.device,&v,nullptr,&view));
    }
    ~Image(){vkDestroyImageView(gpu.device,view,nullptr);vkDestroyImage(gpu.device,image,nullptr);vkFreeMemory(gpu.device,memory,nullptr);}
};
struct Params {std::array<float,12> transform;std::array<float,4> p,pp;std::array<float,2> extent,j,pj;u32 mode;};
struct Compute {
    Device gpu;Buffer staging{gpu,N*32};
    Image depth{gpu,VK_FORMAT_R32G32B32A32_SFLOAT},motion{gpu,VK_FORMAT_R16G16_SFLOAT},object{gpu,VK_FORMAT_R32G32B32A32_SFLOAT};
    VkDescriptorSetLayout descriptors{};VkDescriptorPool descriptor_pool{};VkDescriptorSet set{};VkShaderModule module{};VkPipeline pipeline{};
    explicit Compute(const char* path){
        std::array<VkDescriptorSetLayoutBinding,3> b{};for(unsigned i=0;i<3;++i)b[i]={i,i==1?VK_DESCRIPTOR_TYPE_STORAGE_IMAGE:VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE,1,VK_SHADER_STAGE_COMPUTE_BIT,nullptr};
        VkDescriptorSetLayoutCreateInfo ds{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};ds.bindingCount=3;ds.pBindings=b.data();Check(vkCreateDescriptorSetLayout(gpu.device,&ds,nullptr,&descriptors));
        vkDestroyPipelineLayout(gpu.device,gpu.layout,nullptr);const VkPushConstantRange push{VK_SHADER_STAGE_COMPUTE_BIT,0,sizeof(Params)};
        VkPipelineLayoutCreateInfo l{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};l.setLayoutCount=1;l.pSetLayouts=&descriptors;l.pushConstantRangeCount=1;l.pPushConstantRanges=&push;Check(vkCreatePipelineLayout(gpu.device,&l,nullptr,&gpu.layout));
        const std::array<VkDescriptorPoolSize,2> sizes{{{VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE,2},{VK_DESCRIPTOR_TYPE_STORAGE_IMAGE,1}}};VkDescriptorPoolCreateInfo pc{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};pc.maxSets=1;pc.poolSizeCount=2;pc.pPoolSizes=sizes.data();Check(vkCreateDescriptorPool(gpu.device,&pc,nullptr,&descriptor_pool));
        VkDescriptorSetAllocateInfo da{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};da.descriptorPool=descriptor_pool;da.descriptorSetCount=1;da.pSetLayouts=&descriptors;Check(vkAllocateDescriptorSets(gpu.device,&da,&set));
        std::array<VkDescriptorImageInfo,3> infos{{{VK_NULL_HANDLE,depth.view,VK_IMAGE_LAYOUT_GENERAL},{VK_NULL_HANDLE,motion.view,VK_IMAGE_LAYOUT_GENERAL},{VK_NULL_HANDLE,object.view,VK_IMAGE_LAYOUT_GENERAL}}};std::array<VkWriteDescriptorSet,3> writes{};
        for(unsigned i=0;i<3;++i){writes[i]={VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};writes[i].dstSet=set;writes[i].dstBinding=i;writes[i].descriptorCount=1;writes[i].descriptorType=b[i].descriptorType;writes[i].pImageInfo=&infos[i];}vkUpdateDescriptorSets(gpu.device,3,writes.data(),0,nullptr);
        std::ifstream f(path,std::ios::binary|std::ios::ate);assert(f);const auto bytes=f.tellg();std::vector<u32> code(size_t(bytes)/4);f.seekg(0);f.read(reinterpret_cast<char*>(code.data()),bytes);assert(f);
        VkShaderModuleCreateInfo sm{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};sm.codeSize=code.size()*4;sm.pCode=code.data();Check(vkCreateShaderModule(gpu.device,&sm,nullptr,&module));
        VkComputePipelineCreateInfo cp{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};cp.stage={VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO};cp.stage.stage=VK_SHADER_STAGE_COMPUTE_BIT;cp.stage.module=module;cp.stage.pName="main";cp.layout=gpu.layout;Check(vkCreateComputePipelines(gpu.device,VK_NULL_HANDLE,1,&cp,nullptr,&pipeline));
    }
    ~Compute(){vkDestroyPipeline(gpu.device,pipeline,nullptr);vkDestroyShaderModule(gpu.device,module,nullptr);vkDestroyDescriptorPool(gpu.device,descriptor_pool,nullptr);vkDestroyDescriptorSetLayout(gpu.device,descriptors,nullptr);}
    void Run(const Params& p){
        std::memcpy(staging.mapped,depth_tex.pixels.data(),N*16);std::memcpy(static_cast<char*>(staging.mapped)+N*16,object_tex.pixels.data(),N*16);
        VkCommandBufferAllocateInfo ca{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};ca.commandPool=gpu.pool;ca.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;ca.commandBufferCount=1;VkCommandBuffer cmd{};Check(vkAllocateCommandBuffers(gpu.device,&ca,&cmd));VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};Check(vkBeginCommandBuffer(cmd,&begin));
        std::array<VkImageMemoryBarrier,3> barriers{};unsigned i=0;for(VkImage image:{depth.image,motion.image,object.image}){auto& b=barriers[i++];b={VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};b.srcAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT;b.dstAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT;b.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED;b.newLayout=VK_IMAGE_LAYOUT_GENERAL;b.srcQueueFamilyIndex=b.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;b.image=image;b.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};}vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,0,0,nullptr,0,nullptr,3,barriers.data());
        i=0;for(VkImage image:{depth.image,object.image}){VkBufferImageCopy c{};c.bufferOffset=i++*N*16;c.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1};c.imageExtent={W,H,1};vkCmdCopyBufferToImage(cmd,staging.buffer,image,VK_IMAGE_LAYOUT_GENERAL,1,&c);}
        VkMemoryBarrier ready{VK_STRUCTURE_TYPE_MEMORY_BARRIER};ready.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;ready.dstAccessMask=VK_ACCESS_SHADER_READ_BIT;vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,1,&ready,0,nullptr,0,nullptr);
        vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,gpu.layout,0,1,&set,0,nullptr);vkCmdPushConstants(cmd,gpu.layout,VK_SHADER_STAGE_COMPUTE_BIT,0,sizeof(p),&p);vkCmdDispatch(cmd,(W+7)/8,(H+7)/8,1);
        ready.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT;ready.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT;vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,1,&ready,0,nullptr,0,nullptr);VkBufferImageCopy c{};c.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1};c.imageExtent={W,H,1};vkCmdCopyImageToBuffer(cmd,motion.image,VK_IMAGE_LAYOUT_GENERAL,staging.buffer,1,&c);
        ready.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;ready.dstAccessMask=VK_ACCESS_HOST_READ_BIT;vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&ready,0,nullptr,0,nullptr);Check(vkEndCommandBuffer(cmd));VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.commandBufferCount=1;submit.pCommandBuffers=&cmd;Check(vkQueueSubmit(gpu.queue,1,&submit,VK_NULL_HANDLE));Check(vkQueueWaitIdle(gpu.queue));vkFreeCommandBuffers(gpu.device,gpu.pool,1,&cmd);
    }
};
static float Half(u32 v){const int e=(v>>10)&31;return (v&0x8000?-1.f:1.f)*(e==0?std::ldexp(float(v&1023),-24):std::ldexp(1.f+float(v&1023)/1024.f,e-15));}
int main(int argc,char** argv){
    namespace M=Vulkan::Motion;
    std::unique_ptr<Compute> gpu;if(argc>1)gpu=std::make_unique<Compute>(argv[1]);
    double worst=0,gpu_worst=0;unsigned mismatches=0,checks=0,cases=0;
    for(float sx:{-1.f,1.f})for(float sy:{-1.f,1.f})for(int scenario=0;scenario<6;++scenario){
        const float angle=scenario==0?0.f:scenario%2?.013f:-.009f;
        const float tx=scenario==3?.07f:0.f,ty=scenario==0?.08f:scenario==4?-.08f:.02f;
        mat3 rotation(1.f);rotation[1]=vec3(0,cos(angle),sin(angle));rotation[2]=vec3(0,-sin(angle),cos(angle));
        const vec3 translation(tx,ty,scenario==5?.04f:0.f);const vec4 raw(1.42799f,2.53865f,1.00002f,-.0500679f);
        std::array<float,216> constants{};constants[0]=3000;constants[1]=1.f/3000;constants[4]=W;constants[5]=H;constants[52]=raw.x;constants[57]=raw.y;constants[62]=raw.z;constants[63]=raw.w;
        for(unsigned row=0;row<3;++row){for(unsigned col=0;col<3;++col){constants[8+row*4+col]=rotation[row][col];constants[180+row*4+col]=rotation[col][row];}constants[8+row*4+3]=-(transpose(rotation)*translation)[row];constants[180+row*4+3]=translation[row];}
#if CONTROL
        const auto decoded=M::DecodeSceneCamera(constants);
#else
        const auto decoded=M::DecodeSceneCamera(constants,sx,sy);
#endif
        assert(decoded);proj=make_vec4(decoded->camera.proj.data());prev_proj=proj;
        for(unsigned row=0;row<3;++row)reproject[row]=vec4(rotation[0][row],rotation[1][row],rotation[2][row],translation[row]);
        jitter=vec2(.31f,-.27f);object_tex.pixels.fill(vec4(0));
        std::array<vec2,N> expected;
        for(unsigned y=0;y<H;++y)for(unsigned x=0;x<W;++x){const unsigned at=y*W+x;const vec2 uv=(vec2(x,y)+.5f-jitter)/size;const float z=1.7f+.012f*x+.01f*y;
            // Reference comes from the vertex projection and actual viewport,
            // independent of the production motion decoder's clip convention.
            const vec3 view((2*uv.x-1)*z/(raw.x*sx),(2*uv.y-1)*z/(raw.y*sy),z);
            const vec3 previous=rotation*view+translation;const vec2 previous_pixel=(vec2(previous.x*raw.x*sx,previous.y*raw.y*sy)/previous.z*.5f+.5f)*size;
            expected[at]=previous_pixel-uv*size;depth_tex.pixels[at]=vec4(raw.z+raw.w/z,0,0,0);gl_GlobalInvocationID=uvec3(x,y,0);kernel();
            const double error=length(vec2(motion_img.pixels[at])-expected[at]);worst=std::max(worst,error);mismatches+=error>.002;checks++;
        }
        if(gpu){Params p{};std::memcpy(p.transform.data(),reproject,48);std::memcpy(p.p.data(),&proj,16);std::memcpy(p.pp.data(),&prev_proj,16);p.extent={W,H};p.j={jitter.x,jitter.y};gpu->Run(p);const auto* out=static_cast<const uint16_t*>(gpu->staging.mapped);
            for(unsigned at=0;at<N;++at){const double error=length(vec2(Half(out[at*2]),Half(out[at*2+1]))-expected[at]);gpu_worst=std::max(gpu_worst,error);assert(error<.006);}
        }++cases;
    }
#if CONTROL
    assert(mismatches>checks/4);std::printf("R42 CONTROL: %u/%u vertex-reference mismatches; peak %.5f px (viewport signs, stairs/pitch).\n",mismatches,checks,worst);
#else
    assert(mismatches==0);std::printf("PASS: %u scenes, %u CPU float32 vertex-reference comparisons; peak %.6f px.\n",cases,checks,worst);
    if(gpu)std::printf("PASS: production SPIR-V executed on native Vulkan: %u pixel comparisons; peak %.6f px after RG16F storage.\n",checks,gpu_worst);
#endif
}
