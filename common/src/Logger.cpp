#include "common/Logger.hpp"

Logger::Logger(const std::string& name)
    : m_severityLogger(std::unique_ptr<SeverityLogger>(new SeverityLogger()))
{
    m_severityLogger-> add_attribute("ChannelName",
        attrs::constant<std::string>(name));
}

void Logger::log(ELogLevel logLevel, const std::string& message)
{
    logging::record rec = m_severityLogger->
        open_record(keywords::severity = logLevel);

    if (rec) {
        logging::record_ostream strm(rec);
        strm << message;
        strm.flush();
        m_severityLogger->push_record(boost::move(rec));
    }
}
