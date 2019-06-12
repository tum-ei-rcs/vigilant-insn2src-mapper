#ifndef FLOWGENERATORFACTORY_H
#define FLOWGENERATORFACTORY_H

// this file does not require any change when a new architecture is introduced

#include <assert.h>

#include "bincfg/flow/FlowGenerator.hpp"
#include "bincfg/arch/archs.h"

enum class ETargetArch : int {
    // enum values are generated from the include file
    #define ARCH(a) a,
    #include "bincfg/arch/archs.def"
    #undef ARCH
};

using FGenInstanceFunction = std::function<FlowGenerator*()>;
using FGenMapType = std::map<ETargetArch, FGenInstanceFunction>;

namespace FlowGeneratorFactory {
    FlowGenerator* createFGenerator(ETargetArch targetArch);
    FlowGenerator* createFGenerator(const std::string& arch);

    ///@brief return a list of supported architectures
    std::vector<std::string> getArchList(void);

    /// maps arch enum value to its string
    char const* const arch_str[] = {
        #define ARCH(a) #a,
        #include "bincfg/arch/archs.def"
        #undef ARCH
        0
    };

    /// map of architectures known to the factory
    static const FGenMapType fGenMap {
        // generates the map that is used by the factory
        #define ARCH(a) {ETargetArch::a, [](){ return new a##FlowGenerator; }},
        #include "bincfg/arch/archs.def"
        #undef ARCH
    };
}

#endif /* FLOWGENERATORFACTORY_H */
