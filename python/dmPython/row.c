
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
// documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
// rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
// WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
// OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
// OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#include "row.h"
#include "py_Dameng.h"

#define Row_Check(op) PyObject_TypeCheck(op, &RowType)
#define Row_CheckExact(op) (Py_TYPE(op) == &RowType)

Py_ssize_t 
Text_Size(
    PyObject*   o
)
{
#if PY_MAJOR_VERSION < 3
	if (o && PyString_Check(o))
		return PyString_GET_SIZE(o);
#endif
#if PY_MINOR_VERSION > 11
    return (o && PyUnicode_Check(o)) ? PyUnicode_GET_LENGTH(o) : 0;
#else
	return (o && PyUnicode_Check(o)) ? PyUnicode_GET_SIZE(o) : 0;
#endif
}

PyObject* 
Text_New(
    Py_ssize_t      length
)
{
	// Returns a new, uninitialized String (Python 2) or Unicode object (Python 3) object.
#if PY_MAJOR_VERSION < 3
	return PyString_FromStringAndSize(0, length);
#else
#if PY_MINOR_VERSION > 11
    if (sizeof(Py_UNICODE) == 2)
        //如果Py_UNICODE为16位，则构造2字节的字符串对象
        return PyUnicode_New(length, 65535);
    else
        //如果Py_UNICODE为32位，则构造4字节的字符串对象
        return PyUnicode_New(length, 65536);
#else
	return PyUnicode_FromUnicode(0, length);
#endif
#endif
}

TEXT_T* 
Text_Buffer(
    PyObject*   o
)
{
#if PY_MAJOR_VERSION < 3
	return PyString_AS_STRING(o);
#else
#if PY_MINOR_VERSION > 11
    return (TEXT_T*)PyUnicode_4BYTE_DATA(o);
#else
	return PyUnicode_AS_UNICODE(o);
#endif
#endif
}

void 
FreeRowValues(
    Py_ssize_t      cValues,
    PyObject**      apValues
)
{
	Py_ssize_t i = 0;
    if (apValues)
    {
        for (i = 0; i < cValues; i++)
            Py_XDECREF(apValues[i]);

       PyMem_Free(apValues);
    }
}

static 
void Row_dealloc(
    PyObject*       o
)
{
    // Note: Now that __newobj__ is available, our variables could be zero...

    Row* self = (Row*)o;

    Py_XDECREF(self->description);
    Py_XDECREF(self->map_name_to_index);
    FreeRowValues(self->cValues, self->apValues);
    PyObject_Del(self);
}


Row* 
Row_New(
    PyObject*       description,
    PyObject*       map_name_to_index,
    Py_ssize_t      cValues, 
    PyObject**      apValues
)
{
    // Called by other modules to create rows.  Takes ownership of apValues.

#ifdef _MSC_VER
#pragma warning(disable : 4365)
#endif
    Row* row = PyObject_NEW(Row, &RowType);
#ifdef _MSC_VER
#pragma warning(default : 4365)
#endif

    if (row)
    {
        Py_INCREF(description);
        row->description = description;
        Py_INCREF(map_name_to_index);
        row->map_name_to_index = map_name_to_index;
        row->apValues          = apValues;
        row->cValues           = cValues;
    }
    else
    {
        FreeRowValues(cValues, apValues);
    }

    return row;
}


static 
PyObject* 
Row_getattro(
    PyObject*       o, 
    PyObject*       name
)
{
    // Called to handle 'row.colname'.

    Row* self = (Row*)o;

    PyObject* index = PyDict_GetItem(self->map_name_to_index, name);

    if (index)
    {
#if PY_MAJOR_VERSION < 3
        Py_ssize_t i = PyInt_AsSsize_t(index);
#else
        Py_ssize_t i = PyLong_AsSsize_t(index);
#endif
        Py_INCREF(self->apValues[i]);
        return self->apValues[i];
    }

    return PyObject_GenericGetAttr(o, name);
}


static 
Py_ssize_t 
Row_length(
    PyObject*       self
)
{
    return ((Row*)self)->cValues;
}


static 
int 
Row_contains(
    PyObject*       o, 
    PyObject*       el
)
{
    // Implementation of contains.  The documentation is not good (non-existent?), so I copied the following from the
    // PySequence_Contains documentation: Return -1 if error; 1 if ob in seq; 0 if ob not in seq.

	Py_ssize_t i,c;
    Row* self = (Row*)o;

    sdint2 cmp = 0;

    for (i = 0, c = self->cValues ; cmp == 0 && i < c; ++i)
        cmp = PyObject_RichCompareBool(el, self->apValues[i], Py_EQ);

    return cmp;
}


static 
PyObject* 
Row_item(
    PyObject*       o, 
    Py_ssize_t      i
)
{
    // Apparently, negative indexes are handled by magic ;) -- they never make it here.

    Row* self = (Row*)o;

    if (i < 0 || i >= self->cValues)
    {
        PyErr_SetString(PyExc_IndexError, "tuple index out of range");
        return NULL;
    }

    Py_INCREF(self->apValues[i]);
    return self->apValues[i];
}


static 
int 
Row_ass_item(
    PyObject*       o, 
    Py_ssize_t      i, 
    PyObject*       v
)
{
    // Implements row[i] = value.

    Row* self = (Row*)o;

    if (i < 0 || i >= self->cValues)
    {
        PyErr_SetString(PyExc_IndexError, "Row assignment index out of range");
        return -1;
    }

    Py_XDECREF(self->apValues[i]);
    Py_INCREF(v);
    self->apValues[i] = v;

    return 0;
}


static 
int
Row_setattro(
    PyObject*       o, 
    PyObject*       name, 
    PyObject*       v
)
{
    Row* self = (Row*)o;

    PyObject* index = PyDict_GetItem(self->map_name_to_index, name);

    if (index)
        return Row_ass_item(o, PyLong_AsSsize_t(index), v);

    return PyObject_GenericSetAttr(o, name, v);
}


static 
PyObject*
Row_repr(
    PyObject*       o
)
{
	PyObject	*pieces, *piece, *result, *item;
	Py_ssize_t	length, i, offset;
	TEXT_T		*buffer;
    Row* self = (Row*)o;	

    if (self->cValues == 0)
#if PY_MAJOR_VERSION < 3
      return PyString_FromString("()");
#else
      return PyUnicode_FromString("()");
#endif

   pieces = PyTuple_New(self->cValues);
    if (!pieces)
        return 0;

    length = 2 + (2 * (self->cValues-1)); // parens + ',' separators

    for (i = 0; i < self->cValues; i++)
    {
        piece = PyObject_Repr(self->apValues[i]);
        if (!piece)
            return 0;

        length += Text_Size(piece);

        PyTuple_SET_ITEM(pieces, i, piece);
    }

    if (self->cValues == 1)
    {
        // Need a trailing comma: (value,)
        length += 1;
    }

    result = Text_New(length);
    if (!result)
        return 0;
    buffer = Text_Buffer(result);
    offset = 0;
    buffer[offset++] = '(';
    for (i = 0; i < self->cValues; i++)
    {
        item = PyTuple_GET_ITEM(pieces, i);
        memcpy(&buffer[offset], Text_Buffer(item), Text_Size(item) * sizeof(TEXT_T));
        offset += Text_Size(item);

        if (i != self->cValues-1 || self->cValues == 1)
        {
            buffer[offset++] = ',';  

            if (self->cValues != 1)
            {
                buffer[offset++] = ' ';  
            }
        }
    }
    buffer[offset++] = ')';

    return result;
}


static 
PyObject*
Row_richcompare(
    PyObject*       olhs, 
    PyObject*       orhs, 
    int             op
)
{
	 Row  *lhs, *rhs;
	 PyObject	*p;
	 sdint2	    result;
	 Py_ssize_t i, c;
    if (!Row_Check(olhs) || !Row_Check(orhs))
    {
        Py_INCREF(Py_NotImplemented);
        return Py_NotImplemented;
    }

    lhs = (Row*)olhs;
    rhs = (Row*)orhs;

    if (lhs->cValues != rhs->cValues)
    {
        // Different sizes, so use the same rules as the tuple class.
        switch (op)
        {
        case Py_EQ: result = (lhs->cValues == rhs->cValues); break;
        case Py_GE: result = (lhs->cValues >= rhs->cValues); break;
        case Py_GT: result = (lhs->cValues >  rhs->cValues); break;
        case Py_LE: result = (lhs->cValues <= rhs->cValues); break;
        case Py_LT: result = (lhs->cValues <  rhs->cValues); break;
        case Py_NE: result = (lhs->cValues != rhs->cValues); break;
        default:
            // Can't get here, but don't have a cross-compiler way to silence this.
            result = 0;
        }
        p = result ? Py_True : Py_False;
        Py_INCREF(p);
        return p;
    }

    for (i = 0, c = lhs->cValues; i < c; i++)
        if (!PyObject_RichCompareBool(lhs->apValues[i], rhs->apValues[i], Py_EQ))
            return PyObject_RichCompare(lhs->apValues[i], rhs->apValues[i], op);

    // All items are equal.
    switch (op)
    {
    case Py_EQ:
    case Py_GE:
    case Py_LE:
        Py_RETURN_TRUE;

    case Py_GT:
    case Py_LT:
    case Py_NE:
        break;
    }

    Py_RETURN_FALSE;
}


static 
PyObject*
Row_subscript(
    PyObject*       o,
    PyObject*       key
)
{
    Row* row = (Row*)o;
	PyObject	*result;
	Py_ssize_t i = 0, index;

    if (1)
    {
#if PY_MAJOR_VERSION < 3
		if (PyInt_Check(key)) 
			i = PyInt_AsLong(key);			
		else if (PyLong_Check(key)) 
			i = PyLong_AsLong(key);
#else
        if (PyLong_Check(key)) 
            i = PyLong_AsLong(key);
#endif

        if (i == -1 && PyErr_Occurred())
            return 0;
        if (i < 0)
            i += row->cValues;

        if (i < 0 || i >= row->cValues)
            return PyErr_Format(PyExc_IndexError, "row index out of range index=%d len=%d", (int)i, (int)row->cValues);

        Py_INCREF(row->apValues[i]);
        return row->apValues[i];
    }

    if (PySlice_Check(key))
    {
        Py_ssize_t start, stop, step, slicelength;
#if PY_VERSION_HEX >= 0x03020000
        if (PySlice_GetIndicesEx(key, row->cValues, &start, &stop, &step, &slicelength) < 0)
            return 0;
#else
        if (PySlice_GetIndicesEx((PySliceObject*)key, row->cValues, &start, &stop, &step, &slicelength) < 0)
            return 0;
#endif

        if (slicelength <= 0)
            return PyTuple_New(0);

        if (start == 0 && step == 1 && slicelength == row->cValues)
        {
            Py_INCREF(o);
            return o;
        }

        result = PyTuple_New(slicelength);
        if (!result)
            return 0;
        for (i = 0, index = start; i < slicelength; i++, index += step)
        {
            PyTuple_SET_ITEM(result, i, row->apValues[index]);
            Py_INCREF(row->apValues[index]);
        }
        return result;
    }

    return PyErr_Format(PyExc_TypeError, "row indices must be integers, not %.200s", Py_TYPE(key)->tp_name);
}


static PySequenceMethods row_as_sequence =
{
    Row_length,                 // sq_length
    0,                          // sq_concat
    0,                          // sq_repeat
    Row_item,                   // sq_item
    0,                          // was_sq_slice
    Row_ass_item,               // sq_ass_item
    0,                          // sq_ass_slice
    Row_contains,               // sq_contains
};


static PyMappingMethods row_as_mapping =
{
    Row_length,                 // mp_length
    Row_subscript,              // mp_subscript
    0,                          // mp_ass_subscript
};


static char description_doc[] = "The Cursor.description sequence from the Cursor that created this row.";

static PyMemberDef Row_members[] =
{
    { "cursor_description", T_OBJECT_EX, offsetof(Row, description), READONLY, description_doc },
    { 0 }
};

static char row_doc[] =
    "Row objects are sequence objects that hold query results.\n"
    "\n"
    "They are similar to tuples in that they cannot be resized and new attributes\n"
    "cannot be added, but individual elements can be replaced.  This allows data to\n"
    "be \"fixed up\" after being fetched.  (For example, datetimes may be replaced by\n"
    "those with time zones attached.)\n"
    "\n"
    "  row[0] = row[0].replace(tzinfo=timezone)\n"
    "  print row[0]\n"
    "\n"
    "Additionally, individual values can be optionally be accessed or replaced by\n"
    "name.  Non-alphanumeric characters are replaced with an underscore.\n"
    "\n"
    "  cursor.execute(\"select customer_id, [Name With Spaces] from tmp\")\n"
    "  row = cursor.fetchone()\n"
    "  print row.customer_id, row.Name_With_Spaces\n"
    "\n"
    "If using this non-standard feature, it is often convenient to specifiy the name\n"
    "using the SQL 'as' keyword:\n"
    "\n"
    "  cursor.execute(\"select count(*) as total from tmp\")\n"
    "  row = cursor.fetchone()\n"
    "  print row.total";

PyTypeObject RowType =
{
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.Row",                                           // tp_name
    sizeof(Row),                                            // tp_basicsize
    0,                                                      // tp_itemsize
    Row_dealloc,                                            // tp_dealloc
    0,                                                      // tp_print
    0,                                                      // tp_getattr
    0,                                                      // tp_setattr
    0,                                                      // tp_compare
    Row_repr,                                               // tp_repr
    0,                                                      // tp_as_number
    &row_as_sequence,                                       // tp_as_sequence
    &row_as_mapping,                                        // tp_as_mapping
    0,                                                      // tp_hash
    0,                                                      // tp_call
    0,                                                      // tp_str
    Row_getattro,                                           // tp_getattro
    Row_setattro,                                           // tp_setattro
    0,                                                      // tp_as_buffer
    Py_TPFLAGS_DEFAULT,                                     // tp_flags
    row_doc,                                                // tp_doc
    0,                                                      // tp_traverse
    0,                                                      // tp_clear
    Row_richcompare,                                        // tp_richcompare
    0,                                                      // tp_weaklistoffset
    0,                                                      // tp_iter
    0,                                                      // tp_iternext
    0,                                                      // tp_methods
    Row_members,                                            // tp_members
    // 0,                                                      // tp_getset
    // 0,                                                      // tp_base
    // 0,                                                      // tp_dict
    // 0,                                                      // tp_descr_get
    // 0,                                                      // tp_descr_set
    // 0,                                                      // tp_dictoffset
    // 0,                                                      // tp_init
    // 0,                                                      // tp_alloc
    // 0,                                                      // tp_new
    // 0,                                                      // tp_free
    // 0,                                                      // tp_is_gc
    // 0,                                                      // tp_bases
    // 0,                                                      // tp_mro
    // 0,                                                      // tp_cache
    // 0,                                                      // tp_subclasses
    // 0,                                                      // tp_weaklist
};
