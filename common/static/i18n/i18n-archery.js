let i18n_default_lang = 'cn'
let i18n_default_path = '/static/i18n/lang/'
/*默认语言*/
i18n("[i18n]", {
    defaultLang: i18n_default_lang, // 设置默认语言，
    filePath: i18n_default_path,
    filePrefix: "i18n_",
    fileSuffix: "",
    forever:true,// 默认为 true  保存当前语言，设置为 false 后，每次刷新都为cn
    get: true,
    only: ['value', 'html', 'placeholder', 'title'], // 全局设置i18n-only，默认值：['value', 'html', 'placeholder', 'title']
    callback: function() {
        // console.log("i18n is ready.");
    }
});
$(".lang_btn").click(function (){
    console.log(this.getAttribute('lang'))
    i18n("[i18n]", {
        lang: this.getAttribute('lang'),// 变更语言
        filePath: i18n_default_path,
        forever:true,
        get: true
    });
})