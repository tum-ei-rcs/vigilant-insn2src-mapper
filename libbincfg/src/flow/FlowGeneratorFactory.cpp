#include "bincfg/flow/FlowGeneratorFactory.hpp"
#include <iostream>

/**
 * @brief used to index enum class by its underlying type
 */
template <typename E>
constexpr typename std::underlying_type<E>::type to_underlying(E e) {
    return static_cast<typename std::underlying_type<E>::type>(e);
}

FlowGenerator* FlowGeneratorFactory::createFGenerator(ETargetArch targetArch)
{
    auto it = fGenMap.find(targetArch);

    assert(it != fGenMap.end() && "Unsupported target architecture");

    return it->second();
}

FlowGenerator* FlowGeneratorFactory::createFGenerator(const std::string& arch)
{
    auto it = fGenMap.begin();
    for (; it != fGenMap.end(); ++it) {
        const std::string strarch(arch_str[to_underlying(it->first)]);
        if (arch == strarch) {
            break; // found
        }
    }

    assert(it != fGenMap.end() && "Unsupported target architecture");
    return it->second();
}

std::vector<std::string> FlowGeneratorFactory::getArchList(void) {
    std::vector<std::string> ret;
    for (auto & it : fGenMap) {
        const std::string strarch(arch_str[to_underlying(it.first)]);
        ret.push_back(strarch);
    }
    return ret;
}
