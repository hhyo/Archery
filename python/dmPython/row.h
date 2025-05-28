
/*
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
 * WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
 * OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
 * OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef ROW_H
#define ROW_H

#include "strct.h"
/*
 * Used to make a new row from an array of column values.
 */
Row* 
Row_New(PyObject* description, PyObject* map_name_to_index, Py_ssize_t cValues, PyObject** apValues);

/*
 * Dereferences each object in apValues and frees apValue.  This is the internal format used by rows.
 *
 * cValues: The number of items to free in apValues.
 *
 * apValues: The array of values.  This can be NULL.
 */
void FreeRowValues(Py_ssize_t cValues, PyObject** apValues);

#define Row_Check(op) PyObject_TypeCheck(op, &RowType)
#define Row_CheckExact(op) (Py_TYPE(op) == &RowType)

#endif

