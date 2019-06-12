#ifndef LOGMANAGER_H
#define LOGMANAGER_H

#include <vector>
#include "common/Logger.hpp"

using TextSink = sinks::synchronous_sink<sinks::text_ostream_backend>;
using std::vector;


class LogManager
{
private:
    vector<std::shared_ptr<Logger>> m_loggers;
    static boost::shared_ptr<TextSink> s_consoleSink;
    static bool s_isConsoleSinkInitialized;

    void setupConsoleSink();

public:
    LogManager(vector<std::shared_ptr<Logger>>::size_type initialCapacity = 5);
    std::shared_ptr<ILogger> createLogger(const std::string& name);

    bool isConsoleSinkInitialized() const;
};


#endif /* LOGMANAGER_H */
