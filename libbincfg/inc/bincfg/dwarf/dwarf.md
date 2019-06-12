# DWARF Debugging Information Format **4**

## 1. General description

___

### 1.1 The Debugging Information Entry (**DIE**)

A series of DIE's are used by DWARF for the low-level representation of a source program. Each DIE consists of an *identifying tag* and a series of *attributes*. An entry, or group of entries together, provide a description of a corresponding entity in the source program.

> **DW_TAG_*** specifies the class to which an entry belongs to.  
> **DW_AT_*** define the specific characteristics of the entry.

The debugging information entries are contained in the `.debug_info` and `.debug_types` sections of an object file.

### 1.2 Attribute types and values

Each attribute is characterized by an attribute name.

> * No more than one attribute with a given name may appear in any `DIE`.
> * There are no limitations on the ordering of attributes within a `DIE`.

The complete list of possible attributes can be found in the DWARF Specification.

The value of an attribute, based on the class, is determined as follows:

* For a **constant**, the value of the constant is the value of the attribute.
* For a **reference**, the value is a reference to another entity which specifies the value of the attribute.
* For an **exprloc**, the evaluation of the DWARF expression yields the value of the attribute.

### 1.3 Relationship of Debugging Information Entries

A single `DIE` may *own* an arbitrary number of other debugging entries and may be owned by another debugging entry as well. While the debugging information is represented as a *tree*, other relations among entries exist, for example, an entry may contain references to other entries, forming a graph in this case.

> The nodes of the tree are the debugging entries themselves. Child entries of any node are exactly those `DIE`'s owned by that node.

The tree itself is represented by flattening it in prefix order. Each `DIE` may
or may not have child entries.

> * If an entry does not have children, the next physically succeding entry is a sibling.
> * If an entry has children, the next physically succeding entry is its first child.

A producer may attach a `DW_AT_sibling` attribute to any `DIE` in order to enable consumers to quickly scan chains of sibling entries.

### 1.4 DWARF Expressions

DWARF expressions describe how to compute a value or name a location during debugging of a program. They are expressed in terms of DWARF operations that operate on a stack of values.

* *General Operations*

  Each general operation represents a postfix operation on a simple stack machine.

  * Each element of the stack is the size of an address on the target machine.
  * The value on top of the stack after executing the DWARF expressions is to be taken as the result.

In addition to general operations, there are some operations specific to location descriptions described in the next section.

### 1.5 Location descriptions

Information about the location of program objects is provided by location descriptions. Location descriptions can be either of two forms:

1. *Single location descriptions*, which are a language independent representation of addressing rules of arbitrary complexity build from DWARF expressions and/or other specific DWARF location operations. There are two kinds:

   > 1. **Simple** location descriptions, describing the location of one contiguous piece of an object.
   > 2. **Composite** location descriptions, which describe an object in terms of pieces.

2. *Location lists*, which are used to describe objects that have a limited lifetime or change their location during their lifetime.

Refer to DWARF Specification `Chapter 2.5` for further information.

### 1.6 Code Addresses and Ranges

Any `DIE` describing an entity that has a machine code address or range of addresses, which includes, for example, compilation units and subroutines, may have the following attributes:

* `DW_AT_low_pc` for a single address.
* `DW_AT_low_pc` and `DW_AT_high_pc` for a single contiguous range of addresses.
* `DW_AT_ranges` for a non-contiguous range of addresses.

If an entity has no associated machine code, none of these attributes are specified.

* *Single Address*

  When there is a single address associated with an entity, such as a label or alternate entry point of a subprogram, the `DIE` has a `DW_AT_low_pc` attribute whose value is the relocated address for the entity.

* *Contiguous Address Range*

  The value of `DW_AT_low_pc` attribute is the relocated address of the first instruction associated with the entity. The value of `DW_AT_high_pc` is either an absolute relocated address or a relative offset of the first location past the last instruction associated with the entity.

  The presence of low and hight PC attributes for an entity implies that the code generated for the entity is contiguous and exists totally within the boundaries specified by those two attributes. If that is not the case, no low and high PC attributes should be produced.

* *Non-contiguous Address Ranges*

  When the set of addresses of a `DIE` cannot be described as a single contiguous address range, the entry has a `DW_AT_ranges` attribute whose value indicates the beginning of a range list.

  Range lists are contained in a separate object file section called `.debug_ranges`.

  > * Address range entries in a range list may **not** overlap.  
  > * There is no requirement that the entries be ordered in any particular way.

* *Entry Address*

  > *The entry or first executable instruction generated for an entity, if applicable, is often the lowest addressed instruction of a contiguous range of instructions. In other cases, the entry address needs to be specified **explicitly***.

  Any `DIE` describing an entity that has a range of code addresses may have a `DW_AT_entry_pc` attribute to indicate the first executable instruction within that range of addresses. The value of this attribute is a relocated address. If this attribute is not present, the entry address is assumed to be the same as the value of `DW_AT_low_pc` attribute, if present; otherwise the entry address is unknown.

___

### 1.7 Program scope entries

* *Unit Entries*

  An object file may contain one or more compilation units, of which there are three kinds:

  1. **DW_TAG_compile_unit**

     Typically represents the text and data contributed to an exectuable by a single relocatable object file. It may be derived from several source files, including preprocessed *include files*.

  2. **DW_TAG_partial_unit**

     Typically represents a part of the text and data of a relocatable object file. It may be derived from an *include file*, template instatiation, or other implementation-dependent portion of a compilation.

  3. **DW_TAG_type_unit**

     An object file may contain any number of separate type unit entries, each representing a single complete type definition. Each `TU` must be uniquely identified by a 64-bit signature, stored in the `TU` itself and can be used to reference the type definition from `DIE`'s in other `CU`'s and `TU`'s.

     > Types are not required to be placed in type units. In general, only large types such as structure, class, enumeration, and union types included from header files should be considered for separate type units.

  Except for separate type entries, these entries may be thought of as bounded by ranges of text addresses within the program.

  Compilation unit entries may have attributes such as:

  * `DW_AT_low_pc` and `DW_AT_high_pc` pair of attributes or a `DW_AT_ranges` attribute whose values encode the contiguous or non-contiguous address ranges, respectively, of the machine instructions generated for the compilation unit (`CU`).
  * `DW_AT_name` attribute whose value is a null-terminated string, containing the full or relative path name of the primary source file.
  * `DW_AT_stmt_list` attribute whose value is a section offset to the line number information for this compilation unit. The offset is relative to `.debug_line` section.

  The place where a normal or partial unit is imported is represented by a `DIE` with the tag `DW_TAG_imported_unit`. This `DIE` contains a `DW_AT_import` attribute whose value is a reference to a normal or partial compilation unit.
  > An imported unit entry can be thought of as a *glue* used to relate a partial unit, or a `CU` used as a partial unit, to a place in some other compilation unit.

### 1.8 Subroutine and Entry Point Entries

The following tags are used to describe debugging information for subroutines and entry points:

* `DW_TAG_subprogram` describes a subroutine or function.
* `DW_TAG_inlined_subroutine` desbribes a particular inlined instance of a subroutine or function.
* `DW_TAG_entry_point` describes an alternate entry point.

The subroutine or entry point entry **has** a `DW_AT_name` attribute whose value is a null-terminated string. It *may* also have a `DW_AT_linkage_name` attribute.

If the name of the subroutine described by a `DIE` with the tag `DW_TAG_subprogram` is visible outside of its containing scope, that entry has a `DW_AT_external` attribute, which is a flag.

A subroutine may contain a `DW_AT_main_subprogram` attribute, which is a flag.

#### Return types

If a subroutine or entry point is a function that returns a value, that its `DIE` has a `DW_AT_type` attribute to denote the type returned by that function.
  > `DIE`'s for C void function should not have an attribute for the return type.

#### Subroutine and Entry Point Locations

A **subroutine** `DIE` may have either a `DW_AT_low_pc` and `DW_AT_high_pc` pair of attributes or a `DW_AT_ranges` attribute whose values encode the contiguous or non-contiguous address ranges, respectively, of the machine instructions generated for the subroutine.

> A subroutine may also have a `DW_AT_entry_pc` attribute whose value is the address of the first executable instruction of the subroutine.

An **entry point** `DIE` has a `DW_AT_low_pc` attribute whose value is the relocated address of the first machine instruction generated for the entry point.

> A subroutine `DIE` representing a subroutine declaration that is not also a definition does not have code address or range attributes.

#### Inlinable and Inlined Subroutines

A *declaration* or *definition* of an inlinable subroutine is represented by a `DIE` with the tag `DW_TAG_subprogram`.

The `DIE` for a subroutine that is **explicitly** declared to be available for *inline* expansion or that **was** expanded inline *implicitly* by the compiler has a `DW_AT_inline` attribute whose value is an integer constant in the following set of values:

  | Name | Meaning |
  |---|---|
  |`DW_INL_not_inlined`| Not declared inline nor inlined by the compiler. Equivalent to the absence of the containing `DW_AT_inline` attribute. |
  |`DW_INL_inlined`| Not declared inline but inlined by the compiler. |
  |`DW_INL_declared_not_inlined`| Declared inline but not inlined by the compiler. |
  |`DW_INL_not_inlined`| Declared inline and inlined by the compiler. |

##### Abstract Instances

Any `DIE` that is owned (either directly or indirectly) by a `DIE` that contains the `DW_AT_inline` attribute is referred to as an "*abstract instance **entry***".

Any *subroutine* `DIE` that contains a `DW_AT_inline` attribute whose value is **other** than `DW_INL_not_inlined` is known as "*abstract instance **root***".

Any set of *abstract instance **entries*** that are all children (either *directly* or *indirectly*) of some *abstract instance **root***, together with the ***root*** itself, is known as an "*abstract instance **tree***".
> In the case where an abstract instance ***tree*** is nested within another abstract instance ***tree***, entries in the nested abstract tree are not considered to be entries in the outer abstract instance tree. This means that an abstract instance **root** may be nested in another (outer) abstract instance tree. In this case its children are not considered to be part of the outer abstract instance tree.

A `DIE` that is a member of an abstract instance tree should not contain attributes that describe aspects of a subroutine which vary between distinct inlined expansions or distinct out-of-line expansions, for example the `DW_AT_low_pc`, `DW_AT_high_pc` attributes.

##### Concrete Inlined Instances

Each **inline** expansion of a subroutine is represented by a `DIE` with the tag `DW_TAG_inlined_subroutine`. Each such entry should be a direct child of the entry that represents the scope within which the inlining occurs.

Each inlined subroutine may have either a `DW_AT_low_pc` and `DW_AT_high_pc` pair of attributes or a `DW_AT_ranges` attribute whose values encode the *contiguous* or *non-contiguous* address ranges, respectively, of the machine instructions generated for the inlined subroutine. It may also contain a `DW_AT_entry_pc` attribute.

An inlined subroutine may also have the following attributes:

* `DW_AT_call_file`
* `DW_AT_call_line`
* `DW_AT_call_column`

> These attributes decribe the coordinates of the call, not those of the subroutine declaration.



### 1.9 Line Information

___

## 2. Querying DWARF debugging information using *libdwarf*

### 2.1 Reading line information

### 2.2 Reading address ranges

### 2.3 Reading source files

### 2.4 Reading subprogram information