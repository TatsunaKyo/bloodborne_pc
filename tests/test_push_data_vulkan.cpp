// SPDX-License-Identifier: GPL-2.0-or-later
#include <vulkan/vulkan.h>
#include <array>
#include <vector>
#include <fstream>
#include <cassert>
#include <cstring>
#include <cstdio>
#include <stdexcept>
void check(VkResult r){if(r!=VK_SUCCESS)throw std::runtime_error("Vulkan result "+std::to_string(r));}
int main(int argc,char** argv){
 assert(argc==3);VkInstance instance{};VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};app.apiVersion=VK_API_VERSION_1_2;
 VkInstanceCreateInfo ic{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};ic.pApplicationInfo=&app;check(vkCreateInstance(&ic,nullptr,&instance));
 uint32_t n=0;check(vkEnumeratePhysicalDevices(instance,&n,nullptr));assert(n);std::vector<VkPhysicalDevice> physical(n);check(vkEnumeratePhysicalDevices(instance,&n,physical.data()));auto gpu=physical[0];
 VkPhysicalDeviceProperties properties{};vkGetPhysicalDeviceProperties(gpu,&properties);std::printf("Actual Vulkan compute device: %s\n",properties.deviceName);
 vkGetPhysicalDeviceQueueFamilyProperties(gpu,&n,nullptr);std::vector<VkQueueFamilyProperties> families(n);vkGetPhysicalDeviceQueueFamilyProperties(gpu,&n,families.data());uint32_t family=0;while(!(families.at(family).queueFlags&VK_QUEUE_COMPUTE_BIT))++family;
 float priority=1;VkDeviceQueueCreateInfo q{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};q.queueFamilyIndex=family;q.queueCount=1;q.pQueuePriorities=&priority;
 VkDeviceCreateInfo dc{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};dc.queueCreateInfoCount=1;dc.pQueueCreateInfos=&q;VkDevice device{};check(vkCreateDevice(gpu,&dc,nullptr,&device));VkQueue queue{};vkGetDeviceQueue(device,family,0,&queue);
 VkBufferCreateInfo bc{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};bc.size=4;bc.usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;VkBuffer buffer{};check(vkCreateBuffer(device,&bc,nullptr,&buffer));
 VkMemoryRequirements req{};vkGetBufferMemoryRequirements(device,buffer,&req);VkPhysicalDeviceMemoryProperties mem{};vkGetPhysicalDeviceMemoryProperties(gpu,&mem);uint32_t type=0;
 const auto flags=VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;while(!(req.memoryTypeBits&(1u<<type)) || (mem.memoryTypes[type].propertyFlags&flags)!=flags)++type;assert(type<mem.memoryTypeCount);
 VkMemoryAllocateInfo alloc{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};alloc.allocationSize=req.size;alloc.memoryTypeIndex=type;VkDeviceMemory memory{};check(vkAllocateMemory(device,&alloc,nullptr,&memory));check(vkBindBufferMemory(device,buffer,memory,0));void* mapped=nullptr;check(vkMapMemory(device,memory,0,VK_WHOLE_SIZE,0,&mapped));
 VkDescriptorSetLayoutBinding binding{0,VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1,VK_SHADER_STAGE_COMPUTE_BIT,nullptr};VkDescriptorSetLayoutCreateInfo lc{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};lc.bindingCount=1;lc.pBindings=&binding;VkDescriptorSetLayout set_layout{};check(vkCreateDescriptorSetLayout(device,&lc,nullptr,&set_layout));
 VkDescriptorPoolSize pool_size{VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1};VkDescriptorPoolCreateInfo pc{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};pc.maxSets=1;pc.poolSizeCount=1;pc.pPoolSizes=&pool_size;VkDescriptorPool descriptors{};check(vkCreateDescriptorPool(device,&pc,nullptr,&descriptors));
 VkDescriptorSetAllocateInfo da{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};da.descriptorPool=descriptors;da.descriptorSetCount=1;da.pSetLayouts=&set_layout;VkDescriptorSet set{};check(vkAllocateDescriptorSets(device,&da,&set));VkDescriptorBufferInfo bi{buffer,0,4};VkWriteDescriptorSet write{VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};write.dstSet=set;write.descriptorCount=1;write.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;write.pBufferInfo=&bi;vkUpdateDescriptorSets(device,1,&write,0,nullptr);
 VkPushConstantRange push{VK_SHADER_STAGE_COMPUTE_BIT,0,80};VkPipelineLayoutCreateInfo plc{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};plc.setLayoutCount=1;plc.pSetLayouts=&set_layout;plc.pushConstantRangeCount=1;plc.pPushConstantRanges=&push;VkPipelineLayout layout{};check(vkCreatePipelineLayout(device,&plc,nullptr,&layout));
 VkCommandPoolCreateInfo cp{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};cp.queueFamilyIndex=family;cp.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;VkCommandPool commands{};check(vkCreateCommandPool(device,&cp,nullptr,&commands));VkCommandBufferAllocateInfo ca{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};ca.commandPool=commands;ca.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;ca.commandBufferCount=1;VkCommandBuffer cmd{};check(vkAllocateCommandBuffers(device,&ca,&cmd));
 VkPipelineCacheCreateInfo pci{VK_STRUCTURE_TYPE_PIPELINE_CACHE_CREATE_INFO};VkPipelineCache cache{};check(vkCreatePipelineCache(device,&pci,nullptr,&cache));
 std::array<uint32_t,20> values{};uint32_t expected=0;for(uint32_t i=4;i<18;++i){values[i]=0x01020304u+i;expected+=values[i]*4;}values[18]=0x33445566u;values[19]=0x778899aau;expected+=values[18]+values[19];
 for(int test=1;test<3;++test){
  std::ifstream f(argv[test],std::ios::binary|std::ios::ate);auto size=f.tellg();assert(size>0&&size%4==0);std::vector<uint32_t> words(size_t(size)/4);f.seekg(0);f.read((char*)words.data(),size);
  VkShaderModuleCreateInfo sc{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};sc.codeSize=words.size()*4;sc.pCode=words.data();VkShaderModule shader{};check(vkCreateShaderModule(device,&sc,nullptr,&shader));
  VkComputePipelineCreateInfo cpc{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};cpc.stage.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;cpc.stage.stage=VK_SHADER_STAGE_COMPUTE_BIT;cpc.stage.module=shader;cpc.stage.pName="main";cpc.layout=layout;VkPipeline pipeline{};check(vkCreateComputePipelines(device,cache,1,&cpc,nullptr,&pipeline));
  *(uint32_t*)mapped=0;check(vkResetCommandBuffer(cmd,0));VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};check(vkBeginCommandBuffer(cmd,&begin));vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,1,&set,0,nullptr);vkCmdPushConstants(cmd,layout,VK_SHADER_STAGE_COMPUTE_BIT,0,80,values.data());vkCmdDispatch(cmd,1,1,1);
  VkMemoryBarrier barrier{VK_STRUCTURE_TYPE_MEMORY_BARRIER};barrier.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT;barrier.dstAccessMask=VK_ACCESS_HOST_READ_BIT;vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&barrier,0,nullptr,0,nullptr);check(vkEndCommandBuffer(cmd));VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.commandBufferCount=1;submit.pCommandBuffers=&cmd;check(vkQueueSubmit(queue,1,&submit,VK_NULL_HANDLE));check(vkQueueWaitIdle(queue));assert(*(uint32_t*)mapped==expected);std::printf("PASS %s checksum %08x (all 56 offsets + motion/scene)\n",argv[test],expected);
  size_t cache_size=0;check(vkGetPipelineCacheData(device,cache,&cache_size,nullptr));std::vector<uint8_t> cached(cache_size);check(vkGetPipelineCacheData(device,cache,&cache_size,cached.data()));assert(cache_size>=sizeof(VkPipelineCacheHeaderVersionOne));VkPipelineCacheHeaderVersionOne header{};memcpy(&header,cached.data(),sizeof(header));assert(header.vendorID==properties.vendorID&&header.deviceID==properties.deviceID&&!memcmp(header.pipelineCacheUUID,properties.pipelineCacheUUID,VK_UUID_SIZE));
  vkDestroyPipeline(device,pipeline,nullptr);vkDestroyShaderModule(device,shader,nullptr);vkDestroyPipelineCache(device,cache,nullptr);pci.initialDataSize=cache_size;pci.pInitialData=cached.data();check(vkCreatePipelineCache(device,&pci,nullptr,&cache));
 }
 vkDestroyPipelineCache(device,cache,nullptr);vkDestroyCommandPool(device,commands,nullptr);vkDestroyPipelineLayout(device,layout,nullptr);vkDestroyDescriptorPool(device,descriptors,nullptr);vkDestroyDescriptorSetLayout(device,set_layout,nullptr);vkUnmapMemory(device,memory);vkDestroyBuffer(device,buffer,nullptr);vkFreeMemory(device,memory,nullptr);vkDestroyDevice(device,nullptr);vkDestroyInstance(instance,nullptr);
 std::puts("PASS Vulkan execution and driver pipeline cache roundtrip; software execution is not a target-game or NVIDIA FG result.");
}
