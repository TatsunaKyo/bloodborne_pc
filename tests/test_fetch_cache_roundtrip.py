# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the actual fetch-record serializer against R41's writer and its fix."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = 'a93ce851256ce41acc2953539a2ada3bd12de7f8'
HEADER = 'gpu/shadps4/common/serdes.h'

PREFIX = r'''
#include "common/serdes.h"
#include <cassert>
#include <cstdio>
namespace AmdGpu { struct Buffer {u64 base_address{}; u8 data_format{},num_format{};}; }
namespace Shader { struct Info {template<class T> constexpr T ReadUdReg(u8,u8) const {return {};}};
namespace Gcn {
__DECLARATIONS__
}
__METHODS__
}
int main() {
 unsigned cases=0;
 for(unsigned count:{0u,1u,2u,6u,16u,32u}) for(unsigned suffix:{0u,1u,5u,100u}) {
  Shader::Gcn::FetchShaderData original;
  original.size=0x12345678;original.vertex_offset_sgpr=7;original.instance_offset_sgpr=9;
  original.attributes.resize(count);
  for(unsigned i=0;i<count;++i) {
   auto* bytes=reinterpret_cast<u8*>(&original.attributes[i]);
   for(size_t j=0;j<sizeof(Shader::Gcn::VertexAttribute);++j)bytes[j]=u8(i*17+j+1);
  }
  Serialization::Archive saved;Serialization::Writer writer{saved};
  writer.Write(u64{0x3141592653589793ull});
  original.Serialize(saved);
  std::vector<u8> tail(suffix,0xAB);writer.Write(tail.data(),tail.size());
  auto bytes=saved.TakeOff();
  Serialization::Archive input{std::move(bytes)};Serialization::Reader reader{input};
  u64 prefix{};reader.Read(prefix);assert(prefix==0x3141592653589793ull);
  Shader::Gcn::FetchShaderData recovered;assert(recovered.Deserialize(input));
  assert(recovered.size==original.size && recovered.vertex_offset_sgpr==7 && recovered.instance_offset_sgpr==9);
  assert(recovered.attributes.size()==count);
  for(unsigned i=0;i<count;++i)assert(std::memcmp(&original.attributes[i],&recovered.attributes[i],sizeof(Shader::Gcn::VertexAttribute))==0);
  std::vector<u8> returned(suffix);reader.Read(returned.data(),returned.size());assert(returned==tail);
  assert(input.IsEoS()==bool(CURRENT));++cases;
 }
 std::printf("%s: %u actual fetch-record round trips, all fields and following bytes intact; %s.\n",
             CURRENT?"PASS":"R41 CONTROL",cases,CURRENT?"exact end of record":"unused tails rejected by metadata loader");
}
'''


def main():
    header = (ROOT/'gpu/shadps4/shader_recompiler/frontend/fetch_shader.h').read_text()
    declarations = header[header.index('struct VertexAttribute {'):header.index('const u32* GetFetchShaderCode')]
    source = (ROOT/'gpu/shadps4/video_core/renderer_vulkan/vk_pipeline_serialization.cpp').read_text()
    methods = source[source.index('void Gcn::FetchShaderData::Serialize('):source.index('void PersistentSrtInfo::Serialize(')]
    with tempfile.TemporaryDirectory(prefix='fetch-cache-') as temp:
        folder = Path(temp)
        for current in (False, True):
            include = folder/('current' if current else 'revision41')/'common'
            include.mkdir(parents=True)
            content = ((ROOT/HEADER).read_text() if current else
                       subprocess.check_output(['git','show',BASE+':'+HEADER],cwd=ROOT,text=True))
            (include/'serdes.h').write_text(content)
            cpp = include.parent/'test.cpp'
            cpp.write_text(PREFIX.replace('__DECLARATIONS__', declarations).replace('__METHODS__', methods))
            exe = include.parent/'test'
            subprocess.run(['g++','-std=c++20','-O1','-Wall','-Wextra','-Werror','-DCURRENT='+str(int(current)),
                            '-I'+str(include.parent),'-I'+str(ROOT/'gpu/shadps4'),str(cpp),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)


if __name__ == '__main__':
    main()
