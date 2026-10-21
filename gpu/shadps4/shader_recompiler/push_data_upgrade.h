// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <array>
#include <span>
#include <unordered_map>
#include <vector>
#include <cstdint>
namespace Shader::PushLayout {
// Upgrade the exact R52 40-buffer declaration without discarding translated shaders.
// Offset vector accesses retain their member numbers; scalar motion/scene accesses move.
inline bool Upgrade(std::span<const uint32_t> code, std::vector<uint32_t>& output) {
    using U = uint32_t;
    output.clear();
    if (code.size() < 5 || code[0] != 0x07230203u) return false;
    std::unordered_map<U, std::vector<U>> types;
    std::unordered_map<U, U> constants;
    std::unordered_map<U, std::array<U,9>> offsets;
    U variable=0, block=0, integer=0;
    for (size_t pos=5; pos<code.size();) {
        U n=code[pos]>>16, op=code[pos]&65535;
        if (!n || pos+n>code.size()) return false;
        auto ins=code.subspan(pos,n);
        if ((op==21 || op==23 || op==30 || op==32) && n>=2) types[ins[1]]={ins.begin()+2,ins.end()};
        if (op==21 && n==4 && ins[2]==32 && ins[3]==0) integer=ins[1];
        if (op==43 && n==4 && ins[1]==integer) constants[ins[2]]=ins[3];
        if (op==72 && n==5 && ins[3]==35 && ins[2]<9) {
            auto [it, added]=offsets.try_emplace(ins[1]);
            if (added) it->second.fill(~0u);
            it->second[ins[2]]=ins[4];
        }
        if (op==59 && n>=4 && ins[3]==9) {variable=ins[2]; block=ins[1];}
        pos+=n;
    }
    if (!variable || !types.contains(block) || types[block].size()!=2) return true;
    block=types[block][1];
    if (!types.contains(block) || types[block].size()!=9) return true;
    const auto members=types[block];
    const std::array<U,9> expected{0,4,8,12,16,32,48,72,76};
    if (!offsets.contains(block) || offsets[block]!=expected) return true;
    auto vectorSize=[&](U id,U count){return types.contains(id) && types[id].size()==2 && types[id][0]==integer && types[id][1]==count;};
    if (!integer || !vectorSize(members[4],4) || !vectorSize(members[5],4) || !vectorSize(members[6],2) || members[7]!=integer || members[8]!=integer) return true;
    U bound=code[3];
    U index8=0,index9=0;
    for (const auto& [id,value]:constants) {if(value==8)index8=id;if(value==9)index9=id;}
    const bool new8=!index8,new9=!index9;
    if(new8)index8=bound++;
    if(new9)index9=bound++;
    output.assign(code.begin(),code.begin()+5);output[3]=bound;
    bool inserted=false;
    for(size_t pos=5;pos<code.size();) {
        const U n=code[pos]>>16,op=code[pos]&65535;
        std::vector<U> ins(code.begin()+pos,code.begin()+pos+n);
        if(op==54 && !inserted) {
            if(new8)output.insert(output.end(),{(4u<<16)|43u,integer,index8,8});
            if(new9)output.insert(output.end(),{(4u<<16)|43u,integer,index9,9});
            inserted=true;
        }
        if(op==30 && n==11 && ins[1]==block) {
            ins[0]=(12u<<16)|30u;
            ins[8]=members[4];
            ins.insert(ins.begin()+9,members[6]);
        }
        if((op==72 || op==6) && n>=3 && ins[1]==block && ins[2]>=7)++ins[2];
        if((op==65 || op==66) && n==5 && ins[3]==variable && constants.contains(ins[4])) {
            if(constants[ins[4]]==7)ins[4]=index8;
            else if(constants[ins[4]]==8)ins[4]=index9;
        }
        output.insert(output.end(),ins.begin(),ins.end());
        if(op==72 && n==5 && ins[1]==block && ins[2]==6 && ins[3]==35)
            output.insert(output.end(),{(5u<<16)|72u,block,7,35,64});
        pos+=n;
    }
    return true;
}
}
