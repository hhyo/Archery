(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory())
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory()
    } else {
        root['watermark'] = factory()
    }
}(this, function() {
    var watermark = {};
    var defaultSettings = {
        watermark_id: 'wm_div_id',
        watermark_prefix: 'mask_div_id',
        watermark_txt: "测试水印",
        watermark_x: 50,
        watermark_y: 20,
        watermark_rows: 0,
        watermark_cols: 0,
        watermark_x_space: 100,
        watermark_y_space: 50,
        watermark_font: '微软雅黑',
        watermark_color: 'black',
        watermark_fontsize: '15px',
        watermark_alpha: 0.15,
        watermark_width: 210,
        watermark_height: 80,
        watermark_angle: 20,
        watermark_parent_width: 0,
        watermark_parent_height: 0,
        watermark_parent_node: null,
        monitor: true,
    };
    var loadMark = function(settings) {
        if (arguments.length === 1 && typeof arguments[0] === "object") {
            var src = arguments[0] || {};
            for (key in src) {
                if (src[key] && defaultSettings[key] && src[key] === defaultSettings[key]) continue;
                else if (src[key] || src[key] === 0) defaultSettings[key] = src[key]
            }
        }
        var watermark_element = document.getElementById(defaultSettings.watermark_id);
        watermark_element && watermark_element.parentNode && watermark_element.parentNode.removeChild(watermark_element);
        var watermark_parent_element = document.getElementById(defaultSettings.watermark_parent_node);
        var watermark_hook_element = watermark_parent_element ? watermark_parent_element : document.body;
        var page_width = Math.max(watermark_hook_element.scrollWidth, watermark_hook_element.clientWidth);
        var page_height = Math.max(watermark_hook_element.scrollHeight, watermark_hook_element.clientHeight);
        var setting = arguments[0] || {};
        var parentEle = watermark_hook_element;
        var page_offsetTop = 0;
        var page_offsetLeft = 0;
        if (setting.watermark_parent_width || setting.watermark_parent_height) {
            if (parentEle) {
                page_offsetTop = parentEle.offsetTop || 0;
                page_offsetLeft = parentEle.offsetLeft || 0;
                defaultSettings.watermark_x = defaultSettings.watermark_x + page_offsetLeft;
                defaultSettings.watermark_y = defaultSettings.watermark_y + page_offsetTop
            }
        } else {
            if (parentEle) {
                page_offsetTop = parentEle.offsetTop || 0;
                page_offsetLeft = parentEle.offsetLeft || 0
            }
        }
        var otdiv = document.getElementById(defaultSettings.watermark_id);
        var shadowRoot = null;
        if (!otdiv) {
            otdiv = document.createElement('div');
            otdiv.id = defaultSettings.watermark_id;
            otdiv.setAttribute('style', 'pointer-events: none !important; display: block !important');
            if (typeof otdiv.attachShadow === 'function') {
                shadowRoot = otdiv.attachShadow({
                    mode: 'open'
                })
            } else {
                shadowRoot = otdiv
            }
            var nodeList = watermark_hook_element.children;
            var index = Math.floor(Math.random() * (nodeList.length - 1));
            if (nodeList[index]) {
                watermark_hook_element.insertBefore(otdiv, nodeList[index])
            } else {
                watermark_hook_element.appendChild(otdiv)
            }
        } else if (otdiv.shadowRoot) {
            shadowRoot = otdiv.shadowRoot
        }
        defaultSettings.watermark_cols = parseInt((page_width - defaultSettings.watermark_x) / (defaultSettings.watermark_width + defaultSettings.watermark_x_space));
        var temp_watermark_x_space = parseInt((page_width - defaultSettings.watermark_x - defaultSettings.watermark_width * defaultSettings.watermark_cols) / (defaultSettings.watermark_cols));
        defaultSettings.watermark_x_space = temp_watermark_x_space ? defaultSettings.watermark_x_space : temp_watermark_x_space;
        var allWatermarkWidth;
        defaultSettings.watermark_rows = parseInt((page_height - defaultSettings.watermark_y) / (defaultSettings.watermark_height + defaultSettings.watermark_y_space));
        var temp_watermark_y_space = parseInt((page_height - defaultSettings.watermark_y - defaultSettings.watermark_height * defaultSettings.watermark_rows) / (defaultSettings.watermark_rows));
        defaultSettings.watermark_y_space = temp_watermark_y_space ? defaultSettings.watermark_y_space : temp_watermark_y_space;
        var allWatermarkHeight;
        if (watermark_parent_element) {
            allWatermarkWidth = defaultSettings.watermark_x + defaultSettings.watermark_width * defaultSettings.watermark_cols + defaultSettings.watermark_x_space * (defaultSettings.watermark_cols - 1);
            allWatermarkHeight = defaultSettings.watermark_y + defaultSettings.watermark_height * defaultSettings.watermark_rows + defaultSettings.watermark_y_space * (defaultSettings.watermark_rows - 1)
        } else {
            allWatermarkWidth = page_offsetLeft + defaultSettings.watermark_x + defaultSettings.watermark_width * defaultSettings.watermark_cols + defaultSettings.watermark_x_space * (defaultSettings.watermark_cols - 1);
            allWatermarkHeight = page_offsetTop + defaultSettings.watermark_y + defaultSettings.watermark_height * defaultSettings.watermark_rows + defaultSettings.watermark_y_space * (defaultSettings.watermark_rows - 1)
        }
        var x;
        var y;
        for (var i = 0; i < defaultSettings.watermark_rows; i++) {
            if (watermark_parent_element) {
                y = page_offsetTop + defaultSettings.watermark_y + (page_height - allWatermarkHeight) / 2 + (defaultSettings.watermark_y_space + defaultSettings.watermark_height) * i
            } else {
                y = defaultSettings.watermark_y + (page_height - allWatermarkHeight) / 2 + (defaultSettings.watermark_y_space + defaultSettings.watermark_height) * i
            }
            for (var j = 0; j < defaultSettings.watermark_cols; j++) {
                if (watermark_parent_element) {
                    x = page_offsetLeft + defaultSettings.watermark_x + (page_width - allWatermarkWidth) / 2 + (defaultSettings.watermark_width + defaultSettings.watermark_x_space) * j
                } else {
                    x = defaultSettings.watermark_x + (page_width - allWatermarkWidth) / 2 + (defaultSettings.watermark_width + defaultSettings.watermark_x_space) * j
                }
                var mask_div = document.createElement('div');
                var oText = document.createTextNode(defaultSettings.watermark_txt);
                mask_div.appendChild(oText);
                mask_div.id = defaultSettings.watermark_prefix + i + j;
                mask_div.style.webkitTransform = "rotate(-" + defaultSettings.watermark_angle + "deg)";
                mask_div.style.MozTransform = "rotate(-" + defaultSettings.watermark_angle + "deg)";
                mask_div.style.msTransform = "rotate(-" + defaultSettings.watermark_angle + "deg)";
                mask_div.style.OTransform = "rotate(-" + defaultSettings.watermark_angle + "deg)";
                mask_div.style.transform = "rotate(-" + defaultSettings.watermark_angle + "deg)";
                mask_div.style.visibility = "";
                mask_div.style.position = "absolute";
                mask_div.style.left = x + 'px';
                mask_div.style.top = y + 'px';
                mask_div.style.overflow = "hidden";
                mask_div.style.zIndex = "9999999";
                mask_div.style.opacity = defaultSettings.watermark_alpha;
                mask_div.style.fontSize = defaultSettings.watermark_fontsize;
                mask_div.style.fontFamily = defaultSettings.watermark_font;
                mask_div.style.color = defaultSettings.watermark_color;
                mask_div.style.textAlign = "center";
                mask_div.style.width = defaultSettings.watermark_width + 'px';
                mask_div.style.height = defaultSettings.watermark_height + 'px';
                mask_div.style.display = "block";
                mask_div.style['-ms-user-select'] = "none";
                shadowRoot.appendChild(mask_div)
            }
        }
        const minotor = settings.monitor === undefined ? defaultSettings.monitor : settings.monitor;
        if (minotor) {
            watermarkDom.observe(watermark_hook_element, option);
            watermarkDom.observe(document.getElementById('wm_div_id').shadowRoot, option)
        }
    };
    var removeMark = function() {
        if (arguments.length === 1 && typeof arguments[0] === "object") {
            var src = arguments[0] || {};
            for (key in src) {
                if (src[key] && defaultSettings[key] && src[key] === defaultSettings[key]) continue;
                else if (src[key] || src[key] === 0) defaultSettings[key] = src[key]
            }
        }
        var watermark_element = document.getElementById(defaultSettings.watermark_id);
        var _parentElement = watermark_element.parentNode;
        _parentElement.removeChild(watermark_element)
    };
    var globalSetting;
    watermark.init = function(settings) {
        globalSetting = settings;
        loadMark(settings);
        window.addEventListener('onload', function() {
            loadMark(settings)
        });
        window.addEventListener('resize', function() {
            loadMark(settings)
        })
    };
    watermark.load = function(settings) {
        globalSetting = settings;
        loadMark(settings)
    };
    watermark.remove = function() {
        removeMark()
    };
    var callback = function(records) {
        if ((globalSetting && records.length === 1) || records.length === 1 && records[0].removedNodes.length >= 1) {
            loadMark(globalSetting)
        }
    };
    const MutationObserver = window.MutationObserver || window.WebKitMutationObserver || window.MozMutationObserver;
    var watermarkDom = new MutationObserver(callback);
    var option = {
        'childList': true,
        'attributes': true,
        'subtree': true,
    };
    return watermark
}));

function getNow() {
    var d = new Date();
    var year = d.getFullYear();
    var month = change(d.getMonth() + 1);
    var day = change(d.getDate());
    var hour = change(d.getHours());
    var minute = change(d.getMinutes());
    var second = change(d.getSeconds());

    function change(t) {
        if (t < 10) {
            return "0" + t;
        } else {
            return t;
        }
    }
    var time = year + '-' + month + '-' + day + ' ' + hour + ':' + minute + ':' + second ;
    return time;
}