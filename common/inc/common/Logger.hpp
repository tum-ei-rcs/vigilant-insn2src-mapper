#ifndef LOGGER_H
#define LOGGER_H

#include "common/ILogger.hpp"
#include <memory>

#include <boost/smart_ptr/shared_ptr.hpp>
#include <boost/log/core.hpp>
#include <boost/log/sinks/sync_frontend.hpp>
#include <boost/log/sinks/text_ostream_backend.hpp>
#include <boost/log/sources/severity_logger.hpp>
#include <boost/log/sources/record_ostream.hpp>
#include <boost/log/expressions/formatters/date_time.hpp>
#include <boost/log/support/date_time.hpp>
#include <boost/log/expressions.hpp>
#include <boost/log/utility/setup/common_attributes.hpp>

namespace logging = boost::log;
namespace src = boost::log::sources;
namespace sinks = boost::log::sinks;
namespace attrs = boost::log::attributes;
namespace keywords = boost::log::keywords;
namespace expr = boost::log::expressions;

using SeverityLogger = src::severity_logger<ELogLevel>;


class Logger : public ILogger
{
private:
    std::unique_ptr<SeverityLogger> m_severityLogger;

public:
    Logger(const std::string& name="");
    void log(ELogLevel logLevel, const std::string& message);
};


#endif /* LOGGER_H */
