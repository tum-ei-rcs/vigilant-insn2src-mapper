#include "common/LogManager.hpp"
#include "bincfg/Log.hpp"


int main(int argc, char* argv[])
{
    std::unique_ptr<LogManager> lm(new LogManager());
    bcfg::Log::registerLogger(lm->createLogger("bincfg"));

    bcfg::Log::logi("Hi.");
    bcfg::Log::logd("Hello.");
    bcfg::Log::logw("Warning message.");

    bcfg::Log::setLoggingLevel(ELogLevel::LOG_DEBUG);
    bcfg::Log::logcc("Debug again...");
    bcfg::Log::log(ELogLevel::LOG_CRITICAL, "Critical message");

    return 0;
}