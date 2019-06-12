#ifndef BCFGLOG_H
#define BCFGLOG_H

#include <memory>
#include <sstream>
#include "common/ILogger.hpp"

namespace bcfg {
    class Log;
}

class bcfg::Log
{
private:
    static std::weak_ptr<ILogger> s_logger;
    static ELogLevel              s_currentLevel;
    static std::stringstream      s_lStream;
    static std::ios::fmtflags     s_initialFormatFlags;

    static void resetLogStream();

    // Private constructor
    Log() {} 

public:
    static void registerLogger(std::shared_ptr<ILogger> logger);
    
    // Logging methods
    static void log(ELogLevel level, const std::string& message);
    static void logi(const std::string& message);
    static void logd(const std::string& message);
    static void logw(const std::string& message);
    static void logcc(const std::string& message);
    static void setLoggingLevel(ELogLevel level);

    const static char newl;

    // Singleton
    Log(const Log&)            = delete;
    void operator=(const Log&) = delete;
    static Log& log()
    {
        static Log _log;
        return _log;
    }

    // Overload insertion operator, ELogLevel will flush and reset lStream
    template <typename T>
    friend Log& operator <<(Log& _log, const T& value) {
        if (!s_logger.expired()) {
            s_lStream << value;
        }
        return _log;
    }

    friend Log& operator <<(Log& _log, const ELogLevel& level)
    {
        if (!s_logger.expired()) {
            _log.log(level, s_lStream.str());
            resetLogStream();
        }
        return _log;
    }
};

#endif /* BCFGLOG_H */
