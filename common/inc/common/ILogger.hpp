#ifndef ILOGGER_H
#define ILOGGER_H

#include <string>
#include <ostream>


enum class ELogLevel : std::size_t {
    LOG_INFO     = 0,
    LOG_DEBUG    = 1,
    LOG_WARNING  = 2,
    LOG_ERROR    = 3,
    LOG_CRITICAL = 4
};


std::ostream& operator<< (std::ostream& stream, ELogLevel level);


class ILogger
{
public:
    virtual ~ILogger () {}
    virtual void log (ELogLevel logLevel, const std::string& message) = 0;
};


#endif /* ILOGGER_H */
