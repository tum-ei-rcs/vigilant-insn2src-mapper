#include "common/ILogger.hpp"
#include <map>

std::ostream& operator<< (std::ostream& stream, ELogLevel level)
{
    static const std::map<ELogLevel, std::string> levelMap = {
        {ELogLevel::LOG_INFO,     "INFO"},
        {ELogLevel::LOG_DEBUG,    "DEBG"},
        {ELogLevel::LOG_WARNING,  "WARN"},
        {ELogLevel::LOG_ERROR,    "ERRO"},
        {ELogLevel::LOG_CRITICAL, "CRIT"}};

    if (levelMap.count(level)) {
        stream << levelMap.at(level);
    }
    else {
        stream << static_cast<std::size_t>(level);
    }

    return stream;
}
