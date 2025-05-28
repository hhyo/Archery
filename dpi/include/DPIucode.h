#ifndef _DPI_UCODE_H
#define _DPI_UCODE_H

#ifndef __DPITYPES
#include "DPItypes.h"
#endif

DllExport DPIRETURN
dpi_set_con_attrW(
    dhcon           dpi_hcon,
    sdint4          attr_id,
    dpointer        val,
    sdint4          val_len
);

DllExport DPIRETURN
dpi_get_con_attrW(
    dhcon           dpi_hcon,
    sdint4          attr_id,
    dpointer        val,
    sdint4          buf_len,
    sdint4          *val_len
);

DllExport DPIRETURN
dpi_get_diag_recW(
    sdint2      hndl_type,
    dhandle     hndl,
    sdint2      rec_num,
    sdint4      *err_code,
    sdbyte      *err_msg,
    sdint2      buf_sz,
    sdint2      *msg_len
);

DllExport DPIRETURN
dpi_get_diag_fieldW(
    sdint2      hndl_type,
    dhandle     hndl,
    sdint2      rec_num,
    sdint2      diag_id,
    dpointer    diag_info,
    slength     buf_len,
    slength     *info_len
);

DllExport DPIRETURN
dpi_set_desc_fieldW(
    dhdesc      dpi_desc,
    udint2      rec_num,
    sdint2      field,
    dpointer    val,
    sdint4      val_len
);

DllExport DPIRETURN
dpi_get_desc_fieldW(
    dhdesc      dpi_desc,
    udint2      rec_num,
    sdint2      field,
    dpointer    val,
    sdint4      val_len,
    sdint4*     str_len
);

DllExport DPIRETURN
dpi_get_desc_recW(
    dhdesc      dpi_desc,
    udint2      rec_num,
    sdbyte*     name_buf,
    sdint2      name_buf_len,
    sdint2*     name_len,
    sdint2*     type,
    sdint2*     sub_type,
    slength*    length,
    sdint2*     prec,
    sdint2*     scale,
    sdint2*     nullable
);

DllExport DPIRETURN
dpi_loginW(
    dhcon       dpi_hcon,
    sdbyte*     svr,
    sdbyte*     user,
    sdbyte*     pwd
);

DllExport DPIRETURN
dpi_exec_directW(
    dhstmt      dpi_hstmt,
    sdbyte*     sql_txt,
    sdint4      sqllen
);

DllExport DPIRETURN
dpi_prepareW(
    dhstmt      dpi_hstmt,
    sdbyte*     sql_txt,
    sdint4      sqllen
);

DllExport DPIRETURN
dpi_get_dataW(
    dhstmt          dpi_hstmt,
    udint2          icol,
    sdint2          ctype,
    dpointer        val,
    slength         buf_len,
    slength         *val_len
);

DllExport DPIRETURN
dpi_set_cursor_nameW(
    dhstmt          dpi_hstmt,
    sdbyte*         name,
    sdint2          name_len
);

DllExport DPIRETURN
dpi_get_cursor_nameW(
    dhstmt          dpi_hstmt,
    sdbyte*         name,
    sdint2          buf_len,
    sdint2          *name_len
);

DllExport DPIRETURN
dpi_desc_columnW(
    dhstmt          dpi_hstmt,
    sdint2          icol,
    sdbyte*         name,
    sdint2          buf_len,
    sdint2*         name_len,
    sdint2*         sqltype,
    ulength*        col_sz,
    sdint2*         dec_digits,
    sdint2*         nullable
);

DllExport DPIRETURN
dpi_col_attrW(
    dhstmt          dpi_hstmt,
    udint2          icol,
    udint2          fld_id,
    dpointer        chr_attr,
    sdint2          buf_len,
    sdint2          *chr_attr_len,
    slength         *num_attr
);

DllExport DPIRETURN
dpi_lob_readW(
    dhloblctr       dpi_loblctr,
    ulength         start_pos,
    sdint2          ctype,
    slength         data_to_read,
    dpointer        val_buf,
    slength         buf_len,
    slength*        data_get
);

DllExport DPIRETURN
dpi_lob_readW2(
    dhloblctr       dpi_loblctr,
    udint8          start_pos,
    sdint2          ctype,
    slength         data_to_read,
    dpointer        val_buf,
    slength         buf_len,
    slength*        data_get
);

DllExport DPIRETURN
dpi_lob_readW3(
    dhloblctr       dpi_loblctr,
    udint8          start_pos,
    sdint2          ctype,
    slength         data_to_read,
    dpointer        val_buf,
    slength         buf_len,
    slength*        data_get,
    slength*        data_get_bytes
);

DllExport DPIRETURN
dpi_lob_writeW(
    dhloblctr       dpi_loblctr,
    ulength         start_pos,
    sdint2          ctype,
    dpointer        val,
    ulength         bytes_to_write,
    ulength*        data_writed
);

DllExport DPIRETURN
dpi_lob_writeW2(
    dhloblctr       dpi_loblctr,
    udint8          start_pos,
    sdint2          ctype,
    dpointer        val,
    ulength         bytes_to_write,
    ulength*        data_writed
);

DllExport DPIRETURN
dpi_get_obj_desc_attrW(
    dhobjdesc       obj_desc,
    udint4          nth,
    udint2          attr_id,
    dpointer        buf,
    udint4          buf_len,
    slength*        len
);

////bfile
DllExport
DPIRETURN
dpi_bfile_constructW(
    dhbfile             bfile_lctr,
    udbyte*             dir_name,
    udint4              dir_name_len,
    udbyte*             file_name,
    udint4              file_name_len
);

DllExport
DPIRETURN
dpi_bfile_get_nameW(
    dhbfile             bfile_lctr,
    udbyte*             dir_buf,
    udint4              dir_buf_len,
    udint4*             dir_len,
    udbyte*             file_buf,
    udint4              file_buf_len,
    udint4*             file_len
);

#endif  //_DPI_UCODE_H
