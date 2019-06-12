#include "common/LogManager.hpp"


bool LogManager::s_isConsoleSinkInitialized = false;
boost::shared_ptr<TextSink> LogManager::s_consoleSink =
    boost::make_shared<TextSink>();


LogManager::LogManager(
    vector<std::shared_ptr<Logger>>::size_type initialCapacity)
{
    m_loggers.reserve(initialCapacity);

    // 1. Set up global attributes
    boost::shared_ptr<logging::core> core = logging::core::get();
    core->add_global_attribute("LineID", attrs::counter<std::size_t>(1));
    core->add_global_attribute("TimeStamp", attrs::local_clock());

    // 2. Set up the console sink
    setupConsoleSink();
}


void LogManager::setupConsoleSink()
{
    if (!s_isConsoleSinkInitialized) {
        // Custom formatter (frontend)
        logging::formatter formatter =
            expr::stream
                << "[" << expr::format_date_time<boost::posix_time::ptime>
                    ("TimeStamp", "%H:%M:%S") << "]"
                << " \033[100m " << expr::attr<std::string>("ChannelName")
                << " \033[0m "
                << "<\033[1m" << expr::attr<ELogLevel>("Severity")
                << "\033[0m> "
                << expr::message;

        s_consoleSink->set_formatter(formatter);

        // Acquire lock on the backend and set it up, released when p
        // goes out of scope
        TextSink::locked_backend_ptr p = s_consoleSink->locked_backend();

        // Add the clog ostream to the backend, specify null-op deleter
        p->add_stream(boost::shared_ptr<std::ostream>(&std::clog,
            [](std::ostream*){}));
        
        // Flush the buffers of attached streams after each log record
        // is written, will degrade the logging performance
        p->auto_flush(true);

        // Add the sink to the logging core
        boost::shared_ptr<logging::core> core = logging::core::get();
        core->add_sink(s_consoleSink);

        s_isConsoleSinkInitialized = true;
    }
}


std::shared_ptr<ILogger> LogManager::createLogger(const std::string& name)
{
    std::shared_ptr<Logger> logger = std::make_shared<Logger>(name);
    m_loggers.push_back(std::move(logger));

    return std::static_pointer_cast<ILogger>(m_loggers.back());
}


// Getters
bool LogManager::isConsoleSinkInitialized() const
{
    return s_isConsoleSinkInitialized;
}
