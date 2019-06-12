#include "bincfg/Log.hpp"


std::weak_ptr<ILogger> bcfg::Log::s_logger;
ELogLevel              bcfg::Log::s_currentLevel { ELogLevel::LOG_INFO };
std::stringstream      bcfg::Log::s_lStream;
std::ios::fmtflags     bcfg::Log::s_initialFormatFlags;
const char             bcfg::Log::newl { '\n' };


void bcfg::Log::resetLogStream()
{
    s_lStream.str("");
    s_lStream.clear();
    s_lStream.flags(s_initialFormatFlags);
}


void bcfg::Log::registerLogger(std::shared_ptr<ILogger> logger)
{
    s_logger = logger;
    resetLogStream();
}


void bcfg::Log::log(ELogLevel level, const std::string& message)
{
    if(auto logger = s_logger.lock()) {
        logger->log(level, message);
    }
}


void bcfg::Log::setLoggingLevel(ELogLevel level)
{
    s_currentLevel = level;
}


// Custom
void bcfg::Log::logi(const std::string& message)
{
    log(ELogLevel::LOG_INFO, message);
}


void bcfg::Log::logd(const std::string& message)
{
    log(ELogLevel::LOG_DEBUG, message);
}


void bcfg::Log::logw(const std::string& message)
{
    log(ELogLevel::LOG_WARNING, message);
}


void bcfg::Log::logcc(const std::string& message)
{
    log(s_currentLevel, message);
}