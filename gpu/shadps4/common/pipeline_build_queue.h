// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <condition_variable>
#include <deque>
#include <functional>
#include <mutex>
#include <thread>
#include <vector>
namespace Common {
class PipelineBuildQueue {
public:
 explicit PipelineBuildQueue(unsigned count) {
  for(unsigned i=0;i<count;++i) workers.emplace_back([this]{
   for(;;){std::function<void()> job;
    {std::unique_lock lock(mutex);changed.wait(lock,[this]{return stopping||!jobs.empty();});
     if(jobs.empty())return;job=std::move(jobs.front());jobs.pop_front();++active;}
    job();
    {std::scoped_lock lock(mutex);--active;if(jobs.empty()&&!active)idle.notify_all();}
   }
  });
 }
 ~PipelineBuildQueue(){Stop();}
 bool Submit(std::function<void()> job){std::scoped_lock lock(mutex);if(stopping||jobs.size()>=128)return false;jobs.push_back(std::move(job));changed.notify_one();return true;}
 void Drain(){std::unique_lock lock(mutex);idle.wait(lock,[this]{return jobs.empty()&&!active;});}
 void Stop(){ {std::scoped_lock lock(mutex);stopping=true;}changed.notify_all();for(auto& t:workers)if(t.joinable())t.join();}
private:
 std::mutex mutex;std::condition_variable changed,idle;bool stopping=false;size_t active=0;
 std::deque<std::function<void()>> jobs;std::vector<std::thread> workers;
};
}
