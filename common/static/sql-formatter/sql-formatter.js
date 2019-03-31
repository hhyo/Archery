(function webpackUniversalModuleDefinition(root, factory) {
	if(typeof exports === 'object' && typeof module === 'object')
		module.exports = factory();
	else if(typeof define === 'function' && define.amd)
		define([], factory);
	else if(typeof exports === 'object')
		exports["sqlFormatter"] = factory();
	else
		root["sqlFormatter"] = factory();
})(this, function() {
return /******/ (function(modules) { // webpackBootstrap
/******/ 	// The module cache
/******/ 	var installedModules = {};

/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {

/******/ 		// Check if module is in cache
/******/ 		if(installedModules[moduleId])
/******/ 			return installedModules[moduleId].exports;

/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = installedModules[moduleId] = {
/******/ 			exports: {},
/******/ 			id: moduleId,
/******/ 			loaded: false
/******/ 		};

/******/ 		// Execute the module function
/******/ 		modules[moduleId].call(module.exports, module, module.exports, __webpack_require__);

/******/ 		// Flag the module as loaded
/******/ 		module.loaded = true;

/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}


/******/ 	// expose the modules object (__webpack_modules__)
/******/ 	__webpack_require__.m = modules;

/******/ 	// expose the module cache
/******/ 	__webpack_require__.c = installedModules;

/******/ 	// __webpack_public_path__
/******/ 	__webpack_require__.p = "";

/******/ 	// Load entry module and return exports
/******/ 	return __webpack_require__(0);
/******/ })
/************************************************************************/
/******/ ([
/* 0 */
/***/ (function(module, exports, __webpack_require__) {

	"use strict";

	exports.__esModule = true;

	var _Db2Formatter = __webpack_require__(24);

	var _Db2Formatter2 = _interopRequireDefault(_Db2Formatter);

	var _N1qlFormatter = __webpack_require__(25);

	var _N1qlFormatter2 = _interopRequireDefault(_N1qlFormatter);

	var _PlSqlFormatter = __webpack_require__(26);

	var _PlSqlFormatter2 = _interopRequireDefault(_PlSqlFormatter);

	var _StandardSqlFormatter = __webpack_require__(27);

	var _StandardSqlFormatter2 = _interopRequireDefault(_StandardSqlFormatter);

	function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }

	exports["default"] = {
	    /**
	     * Format whitespaces in a query to make it easier to read.
	     *
	     * @param {String} query
	     * @param {Object} cfg
	     *  @param {String} cfg.language Query language, default is Standard SQL
	     *  @param {String} cfg.indent Characters used for indentation, default is "  " (2 spaces)
	     *  @param {Object} cfg.params Collection of params for placeholder replacement
	     * @return {String}
	     */
	    format: function format(query, cfg) {
	        cfg = cfg || {};

	        switch (cfg.language) {
	            case "db2":
	                return new _Db2Formatter2["default"](cfg).format(query);
	            case "n1ql":
	                return new _N1qlFormatter2["default"](cfg).format(query);
	            case "pl/sql":
	                return new _PlSqlFormatter2["default"](cfg).format(query);
	            case "sql":
	            case undefined:
	                return new _StandardSqlFormatter2["default"](cfg).format(query);
	            default:
	                throw Error("Unsupported SQL dialect: " + cfg.language);
	        }
	    }
	};
	module.exports = exports["default"];

/***/ }),
/* 1 */
/***/ (function(module, exports, __webpack_require__) {

	var freeGlobal = __webpack_require__(12);

	/** Detect free variable `self`. */
	var freeSelf = typeof self == 'object' && self && self.Object === Object && self;

	/** Used as a reference to the global object. */
	var root = freeGlobal || freeSelf || Function('return this')();

	module.exports = root;


/***/ }),
/* 2 */
/***/ (function(module, exports, __webpack_require__) {

	var Symbol = __webpack_require__(9),
	    getRawTag = __webpack_require__(48),
	    objectToString = __webpack_require__(57);

	/** `Object#toString` result references. */
	var nullTag = '[object Null]',
	    undefinedTag = '[object Undefined]';

	/** Built-in value references. */
	var symToStringTag = Symbol ? Symbol.toStringTag : undefined;

	/**
	 * The base implementation of `getTag` without fallbacks for buggy environments.
	 *
	 * @private
	 * @param {*} value The value to query.
	 * @returns {string} Returns the `toStringTag`.
	 */
	function baseGetTag(value) {
	  if (value == null) {
	    return value === undefined ? undefinedTag : nullTag;
	  }
	  return (symToStringTag && symToStringTag in Object(value))
	    ? getRawTag(value)
	    : objectToString(value);
	}

	module.exports = baseGetTag;


/***/ }),
/* 3 */
/***/ (function(module, exports, __webpack_require__) {

	var baseIsNative = __webpack_require__(39),
	    getValue = __webpack_require__(50);

	/**
	 * Gets the native function at `key` of `object`.
	 *
	 * @private
	 * @param {Object} object The object to query.
	 * @param {string} key The key of the method to get.
	 * @returns {*} Returns the function if it's native, else `undefined`.
	 */
	function getNative(object, key) {
	  var value = getValue(object, key);
	  return baseIsNative(value) ? value : undefined;
	}

	module.exports = getNative;


/***/ }),
/* 4 */
/***/ (function(module, exports, __webpack_require__) {

	"use strict";

	exports.__esModule = true;

	var _trimEnd = __webpack_require__(74);

	var _trimEnd2 = _interopRequireDefault(_trimEnd);

	var _tokenTypes = __webpack_require__(8);

	var _tokenTypes2 = _interopRequireDefault(_tokenTypes);

	var _Indentation = __webpack_require__(21);

	var _Indentation2 = _interopRequireDefault(_Indentation);

	var _InlineBlock = __webpack_require__(22);

	var _InlineBlock2 = _interopRequireDefault(_InlineBlock);

	var _Params = __webpack_require__(23);

	var _Params2 = _interopRequireDefault(_Params);

	function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }

	function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

	var Formatter = function () {
	    /**
	     * @param {Object} cfg
	     *   @param {Object} cfg.indent
	     *   @param {Object} cfg.params
	     * @param {Tokenizer} tokenizer
	     */
	    function Formatter(cfg, tokenizer) {
	        _classCallCheck(this, Formatter);

	        this.cfg = cfg || {};
	        this.indentation = new _Indentation2["default"](this.cfg.indent);
	        this.inlineBlock = new _InlineBlock2["default"]();
	        this.params = new _Params2["default"](this.cfg.params);
	        this.tokenizer = tokenizer;
	        this.previousReservedWord = {};
	        this.tokens = [];
	        this.index = 0;
	    }

	    /**
	     * Formats whitespaces in a SQL string to make it easier to read.
	     *
	     * @param {String} query The SQL query string
	     * @return {String} formatted query
	     */


	    Formatter.prototype.format = function format(query) {
	        this.tokens = this.tokenizer.tokenize(query);
	        var formattedQuery = this.getFormattedQueryFromTokens();

	        return formattedQuery.trim();
	    };

	    Formatter.prototype.getFormattedQueryFromTokens = function getFormattedQueryFromTokens() {
	        var _this = this;

	        var formattedQuery = "";

	        this.tokens.forEach(function (token, index) {
	            _this.index = index;

	            if (token.type === _tokenTypes2["default"].WHITESPACE) {
	                // ignore (we do our own whitespace formatting)
	            } else if (token.type === _tokenTypes2["default"].LINE_COMMENT) {
	                formattedQuery = _this.formatLineComment(token, formattedQuery);
	            } else if (token.type === _tokenTypes2["default"].BLOCK_COMMENT) {
	                formattedQuery = _this.formatBlockComment(token, formattedQuery);
	            } else if (token.type === _tokenTypes2["default"].RESERVED_TOPLEVEL) {
	                formattedQuery = _this.formatToplevelReservedWord(token, formattedQuery);
	                _this.previousReservedWord = token;
	            } else if (token.type === _tokenTypes2["default"].RESERVED_NEWLINE) {
	                formattedQuery = _this.formatNewlineReservedWord(token, formattedQuery);
	                _this.previousReservedWord = token;
	            } else if (token.type === _tokenTypes2["default"].RESERVED) {
	                formattedQuery = _this.formatWithSpaces(token, formattedQuery);
	                _this.previousReservedWord = token;
	            } else if (token.type === _tokenTypes2["default"].OPEN_PAREN) {
	                formattedQuery = _this.formatOpeningParentheses(token, formattedQuery);
	            } else if (token.type === _tokenTypes2["default"].CLOSE_PAREN) {
	                formattedQuery = _this.formatClosingParentheses(token, formattedQuery);
	            } else if (token.type === _tokenTypes2["default"].PLACEHOLDER) {
	                formattedQuery = _this.formatPlaceholder(token, formattedQuery);
	            } else if (token.value === ",") {
	                formattedQuery = _this.formatComma(token, formattedQuery);
	            } else if (token.value === ":") {
	                formattedQuery = _this.formatWithSpaceAfter(token, formattedQuery);
	            } else if (token.value === "." || token.value === ";") {
	                formattedQuery = _this.formatWithoutSpaces(token, formattedQuery);
	            } else {
	                formattedQuery = _this.formatWithSpaces(token, formattedQuery);
	            }
	        });
	        return formattedQuery;
	    };

	    Formatter.prototype.formatLineComment = function formatLineComment(token, query) {
	        return this.addNewline(query + token.value);
	    };

	    Formatter.prototype.formatBlockComment = function formatBlockComment(token, query) {
	        return this.addNewline(this.addNewline(query) + this.indentComment(token.value));
	    };

	    Formatter.prototype.indentComment = function indentComment(comment) {
	        return comment.replace(/\n/g, "\n" + this.indentation.getIndent());
	    };

	    Formatter.prototype.formatToplevelReservedWord = function formatToplevelReservedWord(token, query) {
	        this.indentation.decreaseTopLevel();

	        query = this.addNewline(query);

	        this.indentation.increaseToplevel();

	        query += this.equalizeWhitespace(token.value);
	        return this.addNewline(query);
	    };

	    Formatter.prototype.formatNewlineReservedWord = function formatNewlineReservedWord(token, query) {
	        return this.addNewline(query) + this.equalizeWhitespace(token.value) + " ";
	    };

	    // Replace any sequence of whitespace characters with single space


	    Formatter.prototype.equalizeWhitespace = function equalizeWhitespace(string) {
	        return string.replace(/\s+/g, " ");
	    };

	    // Opening parentheses increase the block indent level and start a new line


	    Formatter.prototype.formatOpeningParentheses = function formatOpeningParentheses(token, query) {
	        // Take out the preceding space unless there was whitespace there in the original query
	        // or another opening parens or line comment
	        var preserveWhitespaceFor = [_tokenTypes2["default"].WHITESPACE, _tokenTypes2["default"].OPEN_PAREN, _tokenTypes2["default"].LINE_COMMENT];
	        if (!preserveWhitespaceFor.includes(this.previousToken().type)) {
	            query = (0, _trimEnd2["default"])(query);
	        }
	        query += token.value;

	        this.inlineBlock.beginIfPossible(this.tokens, this.index);

	        if (!this.inlineBlock.isActive()) {
	            this.indentation.increaseBlockLevel();
	            query = this.addNewline(query);
	        }
	        return query;
	    };

	    // Closing parentheses decrease the block indent level


	    Formatter.prototype.formatClosingParentheses = function formatClosingParentheses(token, query) {
	        if (this.inlineBlock.isActive()) {
	            this.inlineBlock.end();
	            return this.formatWithSpaceAfter(token, query);
	        } else {
	            this.indentation.decreaseBlockLevel();
	            return this.formatWithSpaces(token, this.addNewline(query));
	        }
	    };

	    Formatter.prototype.formatPlaceholder = function formatPlaceholder(token, query) {
	        return query + this.params.get(token) + " ";
	    };

	    // Commas start a new line (unless within inline parentheses or SQL "LIMIT" clause)


	    Formatter.prototype.formatComma = function formatComma(token, query) {
	        query = this.trimTrailingWhitespace(query) + token.value + " ";

	        if (this.inlineBlock.isActive()) {
	            return query;
	        } else if (/^LIMIT$/i.test(this.previousReservedWord.value)) {
	            return query;
	        } else {
	            return this.addNewline(query);
	        }
	    };

	    Formatter.prototype.formatWithSpaceAfter = function formatWithSpaceAfter(token, query) {
	        return this.trimTrailingWhitespace(query) + token.value + " ";
	    };

	    Formatter.prototype.formatWithoutSpaces = function formatWithoutSpaces(token, query) {
	        return this.trimTrailingWhitespace(query) + token.value;
	    };

	    Formatter.prototype.formatWithSpaces = function formatWithSpaces(token, query) {
	        return query + token.value + " ";
	    };

	    Formatter.prototype.addNewline = function addNewline(query) {
	        return (0, _trimEnd2["default"])(query) + "\n" + this.indentation.getIndent();
	    };

	    Formatter.prototype.trimTrailingWhitespace = function trimTrailingWhitespace(query) {
	        if (this.previousNonWhitespaceToken().type === _tokenTypes2["default"].LINE_COMMENT) {
	            return (0, _trimEnd2["default"])(query) + "\n";
	        } else {
	            return (0, _trimEnd2["default"])(query);
	        }
	    };

	    Formatter.prototype.previousNonWhitespaceToken = function previousNonWhitespaceToken() {
	        var n = 1;
	        while (this.previousToken(n).type === _tokenTypes2["default"].WHITESPACE) {
	            n++;
	        }
	        return this.previousToken(n);
	    };

	    Formatter.prototype.previousToken = function previousToken() {
	        var offset = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : 1;

	        return this.tokens[this.index - offset] || {};
	    };

	    return Formatter;
	}();

	exports["default"] = Formatter;
	module.exports = exports["default"];

/***/ }),
/* 5 */
/***/ (function(module, exports, __webpack_require__) {

	"use strict";

	exports.__esModule = true;

	var _isEmpty = __webpack_require__(66);

	var _isEmpty2 = _interopRequireDefault(_isEmpty);

	var _escapeRegExp = __webpack_require__(63);

	var _escapeRegExp2 = _interopRequireDefault(_escapeRegExp);

	var _tokenTypes = __webpack_require__(8);

	var _tokenTypes2 = _interopRequireDefault(_tokenTypes);

	function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }

	function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

	var Tokenizer = function () {
	    /**
	     * @param {Object} cfg
	     *  @param {String[]} cfg.reservedWords Reserved words in SQL
	     *  @param {String[]} cfg.reservedToplevelWords Words that are set to new line separately
	     *  @param {String[]} cfg.reservedNewlineWords Words that are set to newline
	     *  @param {String[]} cfg.stringTypes String types to enable: "", '', ``, [], N''
	     *  @param {String[]} cfg.openParens Opening parentheses to enable, like (, [
	     *  @param {String[]} cfg.closeParens Closing parentheses to enable, like ), ]
	     *  @param {String[]} cfg.indexedPlaceholderTypes Prefixes for indexed placeholders, like ?
	     *  @param {String[]} cfg.namedPlaceholderTypes Prefixes for named placeholders, like @ and :
	     *  @param {String[]} cfg.lineCommentTypes Line comments to enable, like # and --
	     *  @param {String[]} cfg.specialWordChars Special chars that can be found inside of words, like @ and #
	     */
	    function Tokenizer(cfg) {
	        _classCallCheck(this, Tokenizer);

	        this.WHITESPACE_REGEX = /^(\s+)/;
	        this.NUMBER_REGEX = /^((-\s*)?[0-9]+(\.[0-9]+)?|0x[0-9a-fA-F]+|0b[01]+)\b/;
	        this.OPERATOR_REGEX = /^(!=|<>|==|<=|>=|!<|!>|\|\||::|->>|->|~~\*|~~|!~~\*|!~~|~\*|!~\*|!~|.)/;

	        this.BLOCK_COMMENT_REGEX = /^(\/\*[^]*?(?:\*\/|$))/;
	        this.LINE_COMMENT_REGEX = this.createLineCommentRegex(cfg.lineCommentTypes);

	        this.RESERVED_TOPLEVEL_REGEX = this.createReservedWordRegex(cfg.reservedToplevelWords);
	        this.RESERVED_NEWLINE_REGEX = this.createReservedWordRegex(cfg.reservedNewlineWords);
	        this.RESERVED_PLAIN_REGEX = this.createReservedWordRegex(cfg.reservedWords);

	        this.WORD_REGEX = this.createWordRegex(cfg.specialWordChars);
	        this.STRING_REGEX = this.createStringRegex(cfg.stringTypes);

	        this.OPEN_PAREN_REGEX = this.createParenRegex(cfg.openParens);
	        this.CLOSE_PAREN_REGEX = this.createParenRegex(cfg.closeParens);

	        this.INDEXED_PLACEHOLDER_REGEX = this.createPlaceholderRegex(cfg.indexedPlaceholderTypes, "[0-9]*");
	        this.IDENT_NAMED_PLACEHOLDER_REGEX = this.createPlaceholderRegex(cfg.namedPlaceholderTypes, "[a-zA-Z0-9._$]+");
	        this.STRING_NAMED_PLACEHOLDER_REGEX = this.createPlaceholderRegex(cfg.namedPlaceholderTypes, this.createStringPattern(cfg.stringTypes));
	    }

	    Tokenizer.prototype.createLineCommentRegex = function createLineCommentRegex(lineCommentTypes) {
	        return new RegExp("^((?:" + lineCommentTypes.map(function (c) {
	            return (0, _escapeRegExp2["default"])(c);
	        }).join("|") + ").*?(?:\n|$))");
	    };

	    Tokenizer.prototype.createReservedWordRegex = function createReservedWordRegex(reservedWords) {
	        var reservedWordsPattern = reservedWords.join("|").replace(/ /g, "\\s+");
	        return new RegExp("^(" + reservedWordsPattern + ")\\b", "i");
	    };

	    Tokenizer.prototype.createWordRegex = function createWordRegex() {
	        var specialChars = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : [];

	        return new RegExp("^([\\w" + specialChars.join("") + "]+)");
	    };

	    Tokenizer.prototype.createStringRegex = function createStringRegex(stringTypes) {
	        return new RegExp("^(" + this.createStringPattern(stringTypes) + ")");
	    };

	    // This enables the following string patterns:
	    // 1. backtick quoted string using `` to escape
	    // 2. square bracket quoted string (SQL Server) using ]] to escape
	    // 3. double quoted string using "" or \" to escape
	    // 4. single quoted string using '' or \' to escape
	    // 5. national character quoted string using N'' or N\' to escape


	    Tokenizer.prototype.createStringPattern = function createStringPattern(stringTypes) {
	        var patterns = {
	            "``": "((`[^`]*($|`))+)",
	            "[]": "((\\[[^\\]]*($|\\]))(\\][^\\]]*($|\\]))*)",
	            "\"\"": "((\"[^\"\\\\]*(?:\\\\.[^\"\\\\]*)*(\"|$))+)",
	            "''": "(('[^'\\\\]*(?:\\\\.[^'\\\\]*)*('|$))+)",
	            "N''": "((N'[^N'\\\\]*(?:\\\\.[^N'\\\\]*)*('|$))+)"
	        };

	        return stringTypes.map(function (t) {
	            return patterns[t];
	        }).join("|");
	    };

	    Tokenizer.prototype.createParenRegex = function createParenRegex(parens) {
	        var _this = this;

	        return new RegExp("^(" + parens.map(function (p) {
	            return _this.escapeParen(p);
	        }).join("|") + ")", "i");
	    };

	    Tokenizer.prototype.escapeParen = function escapeParen(paren) {
	        if (paren.length === 1) {
	            // A single punctuation character
	            return (0, _escapeRegExp2["default"])(paren);
	        } else {
	            // longer word
	            return "\\b" + paren + "\\b";
	        }
	    };

	    Tokenizer.prototype.createPlaceholderRegex = function createPlaceholderRegex(types, pattern) {
	        if ((0, _isEmpty2["default"])(types)) {
	            return false;
	        }
	        var typesRegex = types.map(_escapeRegExp2["default"]).join("|");

	        return new RegExp("^((?:" + typesRegex + ")(?:" + pattern + "))");
	    };

	    /**
	     * Takes a SQL string and breaks it into tokens.
	     * Each token is an object with type and value.
	     *
	     * @param {String} input The SQL string
	     * @return {Object[]} tokens An array of tokens.
	     *  @return {String} token.type
	     *  @return {String} token.value
	     */


	    Tokenizer.prototype.tokenize = function tokenize(input) {
	        var tokens = [];
	        var token = void 0;

	        // Keep processing the string until it is empty
	        while (input.length) {
	            // Get the next token and the token type
	            token = this.getNextToken(input, token);
	            // Advance the string
	            input = input.substring(token.value.length);

	            tokens.push(token);
	        }
	        return tokens;
	    };

	    Tokenizer.prototype.getNextToken = function getNextToken(input, previousToken) {
	        return this.getWhitespaceToken(input) || this.getCommentToken(input) || this.getStringToken(input) || this.getOpenParenToken(input) || this.getCloseParenToken(input) || this.getPlaceholderToken(input) || this.getNumberToken(input) || this.getReservedWordToken(input, previousToken) || this.getWordToken(input) || this.getOperatorToken(input);
	    };

	    Tokenizer.prototype.getWhitespaceToken = function getWhitespaceToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].WHITESPACE,
	            regex: this.WHITESPACE_REGEX
	        });
	    };

	    Tokenizer.prototype.getCommentToken = function getCommentToken(input) {
	        return this.getLineCommentToken(input) || this.getBlockCommentToken(input);
	    };

	    Tokenizer.prototype.getLineCommentToken = function getLineCommentToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].LINE_COMMENT,
	            regex: this.LINE_COMMENT_REGEX
	        });
	    };

	    Tokenizer.prototype.getBlockCommentToken = function getBlockCommentToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].BLOCK_COMMENT,
	            regex: this.BLOCK_COMMENT_REGEX
	        });
	    };

	    Tokenizer.prototype.getStringToken = function getStringToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].STRING,
	            regex: this.STRING_REGEX
	        });
	    };

	    Tokenizer.prototype.getOpenParenToken = function getOpenParenToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].OPEN_PAREN,
	            regex: this.OPEN_PAREN_REGEX
	        });
	    };

	    Tokenizer.prototype.getCloseParenToken = function getCloseParenToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].CLOSE_PAREN,
	            regex: this.CLOSE_PAREN_REGEX
	        });
	    };

	    Tokenizer.prototype.getPlaceholderToken = function getPlaceholderToken(input) {
	        return this.getIdentNamedPlaceholderToken(input) || this.getStringNamedPlaceholderToken(input) || this.getIndexedPlaceholderToken(input);
	    };

	    Tokenizer.prototype.getIdentNamedPlaceholderToken = function getIdentNamedPlaceholderToken(input) {
	        return this.getPlaceholderTokenWithKey({
	            input: input,
	            regex: this.IDENT_NAMED_PLACEHOLDER_REGEX,
	            parseKey: function parseKey(v) {
	                return v.slice(1);
	            }
	        });
	    };

	    Tokenizer.prototype.getStringNamedPlaceholderToken = function getStringNamedPlaceholderToken(input) {
	        var _this2 = this;

	        return this.getPlaceholderTokenWithKey({
	            input: input,
	            regex: this.STRING_NAMED_PLACEHOLDER_REGEX,
	            parseKey: function parseKey(v) {
	                return _this2.getEscapedPlaceholderKey({ key: v.slice(2, -1), quoteChar: v.slice(-1) });
	            }
	        });
	    };

	    Tokenizer.prototype.getIndexedPlaceholderToken = function getIndexedPlaceholderToken(input) {
	        return this.getPlaceholderTokenWithKey({
	            input: input,
	            regex: this.INDEXED_PLACEHOLDER_REGEX,
	            parseKey: function parseKey(v) {
	                return v.slice(1);
	            }
	        });
	    };

	    Tokenizer.prototype.getPlaceholderTokenWithKey = function getPlaceholderTokenWithKey(_ref) {
	        var input = _ref.input,
	            regex = _ref.regex,
	            parseKey = _ref.parseKey;

	        var token = this.getTokenOnFirstMatch({ input: input, regex: regex, type: _tokenTypes2["default"].PLACEHOLDER });
	        if (token) {
	            token.key = parseKey(token.value);
	        }
	        return token;
	    };

	    Tokenizer.prototype.getEscapedPlaceholderKey = function getEscapedPlaceholderKey(_ref2) {
	        var key = _ref2.key,
	            quoteChar = _ref2.quoteChar;

	        return key.replace(new RegExp((0, _escapeRegExp2["default"])("\\") + quoteChar, "g"), quoteChar);
	    };

	    // Decimal, binary, or hex numbers


	    Tokenizer.prototype.getNumberToken = function getNumberToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].NUMBER,
	            regex: this.NUMBER_REGEX
	        });
	    };

	    // Punctuation and symbols


	    Tokenizer.prototype.getOperatorToken = function getOperatorToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].OPERATOR,
	            regex: this.OPERATOR_REGEX
	        });
	    };

	    Tokenizer.prototype.getReservedWordToken = function getReservedWordToken(input, previousToken) {
	        // A reserved word cannot be preceded by a "."
	        // this makes it so in "mytable.from", "from" is not considered a reserved word
	        if (previousToken && previousToken.value && previousToken.value === ".") {
	            return;
	        }
	        return this.getToplevelReservedToken(input) || this.getNewlineReservedToken(input) || this.getPlainReservedToken(input);
	    };

	    Tokenizer.prototype.getToplevelReservedToken = function getToplevelReservedToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].RESERVED_TOPLEVEL,
	            regex: this.RESERVED_TOPLEVEL_REGEX
	        });
	    };

	    Tokenizer.prototype.getNewlineReservedToken = function getNewlineReservedToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].RESERVED_NEWLINE,
	            regex: this.RESERVED_NEWLINE_REGEX
	        });
	    };

	    Tokenizer.prototype.getPlainReservedToken = function getPlainReservedToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].RESERVED,
	            regex: this.RESERVED_PLAIN_REGEX
	        });
	    };

	    Tokenizer.prototype.getWordToken = function getWordToken(input) {
	        return this.getTokenOnFirstMatch({
	            input: input,
	            type: _tokenTypes2["default"].WORD,
	            regex: this.WORD_REGEX
	        });
	    };

	    Tokenizer.prototype.getTokenOnFirstMatch = function getTokenOnFirstMatch(_ref3) {
	        var input = _ref3.input,
	            type = _ref3.type,
	            regex = _ref3.regex;

	        var matches = input.match(regex);

	        if (matches) {
	            return { type: type, value: matches[1] };
	        }
	    };

	    return Tokenizer;
	}();

	exports["default"] = Tokenizer;
	module.exports = exports["default"];

/***/ }),
/* 6 */
/***/ (function(module, exports) {

	/**
	 * Checks if `value` is the
	 * [language type](http://www.ecma-international.org/ecma-262/7.0/#sec-ecmascript-language-types)
	 * of `Object`. (e.g. arrays, functions, objects, regexes, `new Number(0)`, and `new String('')`)
	 *
	 * @static
	 * @memberOf _
	 * @since 0.1.0
	 * @category Lang
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is an object, else `false`.
	 * @example
	 *
	 * _.isObject({});
	 * // => true
	 *
	 * _.isObject([1, 2, 3]);
	 * // => true
	 *
	 * _.isObject(_.noop);
	 * // => true
	 *
	 * _.isObject(null);
	 * // => false
	 */
	function isObject(value) {
	  var type = typeof value;
	  return value != null && (type == 'object' || type == 'function');
	}

	module.exports = isObject;


/***/ }),
/* 7 */
/***/ (function(module, exports) {

	/**
	 * Checks if `value` is object-like. A value is object-like if it's not `null`
	 * and has a `typeof` result of "object".
	 *
	 * @static
	 * @memberOf _
	 * @since 4.0.0
	 * @category Lang
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is object-like, else `false`.
	 * @example
	 *
	 * _.isObjectLike({});
	 * // => true
	 *
	 * _.isObjectLike([1, 2, 3]);
	 * // => true
	 *
	 * _.isObjectLike(_.noop);
	 * // => false
	 *
	 * _.isObjectLike(null);
	 * // => false
	 */
	function isObjectLike(value) {
	  return value != null && typeof value == 'object';
	}

	module.exports = isObjectLike;


/***/ }),
/* 8 */
/***/ (function(module, exports) {

	"use strict";

	exports.__esModule = true;
	/**
	 * Constants for token types
	 */
	exports["default"] = {
	    WHITESPACE: "whitespace",
	    WORD: "word",
	    STRING: "string",
	    RESERVED: "reserved",
	    RESERVED_TOPLEVEL: "reserved-toplevel",
	    RESERVED_NEWLINE: "reserved-newline",
	    OPERATOR: "operator",
	    OPEN_PAREN: "open-paren",
	    CLOSE_PAREN: "close-paren",
	    LINE_COMMENT: "line-comment",
	    BLOCK_COMMENT: "block-comment",
	    NUMBER: "number",
	    PLACEHOLDER: "placeholder"
	};
	module.exports = exports["default"];

/***/ }),
/* 9 */
/***/ (function(module, exports, __webpack_require__) {

	var root = __webpack_require__(1);

	/** Built-in value references. */
	var Symbol = root.Symbol;

	module.exports = Symbol;


/***/ }),
/* 10 */
/***/ (function(module, exports, __webpack_require__) {

	var baseToString = __webpack_require__(11);

	/**
	 * Converts `value` to a string. An empty string is returned for `null`
	 * and `undefined` values. The sign of `-0` is preserved.
	 *
	 * @static
	 * @memberOf _
	 * @since 4.0.0
	 * @category Lang
	 * @param {*} value The value to convert.
	 * @returns {string} Returns the converted string.
	 * @example
	 *
	 * _.toString(null);
	 * // => ''
	 *
	 * _.toString(-0);
	 * // => '-0'
	 *
	 * _.toString([1, 2, 3]);
	 * // => '1,2,3'
	 */
	function toString(value) {
	  return value == null ? '' : baseToString(value);
	}

	module.exports = toString;


/***/ }),
/* 11 */
/***/ (function(module, exports, __webpack_require__) {

	var Symbol = __webpack_require__(9),
	    arrayMap = __webpack_require__(33),
	    isArray = __webpack_require__(15),
	    isSymbol = __webpack_require__(19);

	/** Used as references for various `Number` constants. */
	var INFINITY = 1 / 0;

	/** Used to convert symbols to primitives and strings. */
	var symbolProto = Symbol ? Symbol.prototype : undefined,
	    symbolToString = symbolProto ? symbolProto.toString : undefined;

	/**
	 * The base implementation of `_.toString` which doesn't convert nullish
	 * values to empty strings.
	 *
	 * @private
	 * @param {*} value The value to process.
	 * @returns {string} Returns the string.
	 */
	function baseToString(value) {
	  // Exit early for strings to avoid a performance hit in some environments.
	  if (typeof value == 'string') {
	    return value;
	  }
	  if (isArray(value)) {
	    // Recursively convert values (susceptible to call stack limits).
	    return arrayMap(value, baseToString) + '';
	  }
	  if (isSymbol(value)) {
	    return symbolToString ? symbolToString.call(value) : '';
	  }
	  var result = (value + '');
	  return (result == '0' && (1 / value) == -INFINITY) ? '-0' : result;
	}

	module.exports = baseToString;


/***/ }),
/* 12 */
/***/ (function(module, exports) {

	/* WEBPACK VAR INJECTION */(function(global) {/** Detect free variable `global` from Node.js. */
	var freeGlobal = typeof global == 'object' && global && global.Object === Object && global;

	module.exports = freeGlobal;

	/* WEBPACK VAR INJECTION */}.call(exports, (function() { return this; }())))

/***/ }),
/* 13 */
/***/ (function(module, exports) {

	/** Used for built-in method references. */
	var objectProto = Object.prototype;

	/**
	 * Checks if `value` is likely a prototype object.
	 *
	 * @private
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is a prototype, else `false`.
	 */
	function isPrototype(value) {
	  var Ctor = value && value.constructor,
	      proto = (typeof Ctor == 'function' && Ctor.prototype) || objectProto;

	  return value === proto;
	}

	module.exports = isPrototype;


/***/ }),
/* 14 */
/***/ (function(module, exports) {

	/** Used for built-in method references. */
	var funcProto = Function.prototype;

	/** Used to resolve the decompiled source of functions. */
	var funcToString = funcProto.toString;

	/**
	 * Converts `func` to its source code.
	 *
	 * @private
	 * @param {Function} func The function to convert.
	 * @returns {string} Returns the source code.
	 */
	function toSource(func) {
	  if (func != null) {
	    try {
	      return funcToString.call(func);
	    } catch (e) {}
	    try {
	      return (func + '');
	    } catch (e) {}
	  }
	  return '';
	}

	module.exports = toSource;


/***/ }),
/* 15 */
/***/ (function(module, exports) {

	/**
	 * Checks if `value` is classified as an `Array` object.
	 *
	 * @static
	 * @memberOf _
	 * @since 0.1.0
	 * @category Lang
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is an array, else `false`.
	 * @example
	 *
	 * _.isArray([1, 2, 3]);
	 * // => true
	 *
	 * _.isArray(document.body.children);
	 * // => false
	 *
	 * _.isArray('abc');
	 * // => false
	 *
	 * _.isArray(_.noop);
	 * // => false
	 */
	var isArray = Array.isArray;

	module.exports = isArray;


/***/ }),
/* 16 */
/***/ (function(module, exports, __webpack_require__) {

	var isFunction = __webpack_require__(17),
	    isLength = __webpack_require__(18);

	/**
	 * Checks if `value` is array-like. A value is considered array-like if it's
	 * not a function and has a `value.length` that's an integer greater than or
	 * equal to `0` and less than or equal to `Number.MAX_SAFE_INTEGER`.
	 *
	 * @static
	 * @memberOf _
	 * @since 4.0.0
	 * @category Lang
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is array-like, else `false`.
	 * @example
	 *
	 * _.isArrayLike([1, 2, 3]);
	 * // => true
	 *
	 * _.isArrayLike(document.body.children);
	 * // => true
	 *
	 * _.isArrayLike('abc');
	 * // => true
	 *
	 * _.isArrayLike(_.noop);
	 * // => false
	 */
	function isArrayLike(value) {
	  return value != null && isLength(value.length) && !isFunction(value);
	}

	module.exports = isArrayLike;


/***/ }),
/* 17 */
/***/ (function(module, exports, __webpack_require__) {

	var baseGetTag = __webpack_require__(2),
	    isObject = __webpack_require__(6);

	/** `Object#toString` result references. */
	var asyncTag = '[object AsyncFunction]',
	    funcTag = '[object Function]',
	    genTag = '[object GeneratorFunction]',
	    proxyTag = '[object Proxy]';

	/**
	 * Checks if `value` is classified as a `Function` object.
	 *
	 * @static
	 * @memberOf _
	 * @since 0.1.0
	 * @category Lang
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is a function, else `false`.
	 * @example
	 *
	 * _.isFunction(_);
	 * // => true
	 *
	 * _.isFunction(/abc/);
	 * // => false
	 */
	function isFunction(value) {
	  if (!isObject(value)) {
	    return false;
	  }
	  // The use of `Object#toString` avoids issues with the `typeof` operator
	  // in Safari 9 which returns 'object' for typed arrays and other constructors.
	  var tag = baseGetTag(value);
	  return tag == funcTag || tag == genTag || tag == asyncTag || tag == proxyTag;
	}

	module.exports = isFunction;


/***/ }),
/* 18 */
/***/ (function(module, exports) {

	/** Used as references for various `Number` constants. */
	var MAX_SAFE_INTEGER = 9007199254740991;

	/**
	 * Checks if `value` is a valid array-like length.
	 *
	 * **Note:** This method is loosely based on
	 * [`ToLength`](http://ecma-international.org/ecma-262/7.0/#sec-tolength).
	 *
	 * @static
	 * @memberOf _
	 * @since 4.0.0
	 * @category Lang
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is a valid length, else `false`.
	 * @example
	 *
	 * _.isLength(3);
	 * // => true
	 *
	 * _.isLength(Number.MIN_VALUE);
	 * // => false
	 *
	 * _.isLength(Infinity);
	 * // => false
	 *
	 * _.isLength('3');
	 * // => false
	 */
	function isLength(value) {
	  return typeof value == 'number' &&
	    value > -1 && value % 1 == 0 && value <= MAX_SAFE_INTEGER;
	}

	module.exports = isLength;


/***/ }),
/* 19 */
/***/ (function(module, exports, __webpack_require__) {

	var baseGetTag = __webpack_require__(2),
	    isObjectLike = __webpack_require__(7);

	/** `Object#toString` result references. */
	var symbolTag = '[object Symbol]';

	/**
	 * Checks if `value` is classified as a `Symbol` primitive or object.
	 *
	 * @static
	 * @memberOf _
	 * @since 4.0.0
	 * @category Lang
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is a symbol, else `false`.
	 * @example
	 *
	 * _.isSymbol(Symbol.iterator);
	 * // => true
	 *
	 * _.isSymbol('abc');
	 * // => false
	 */
	function isSymbol(value) {
	  return typeof value == 'symbol' ||
	    (isObjectLike(value) && baseGetTag(value) == symbolTag);
	}

	module.exports = isSymbol;


/***/ }),
/* 20 */
/***/ (function(module, exports) {

	module.exports = function(module) {
		if(!module.webpackPolyfill) {
			module.deprecate = function() {};
			module.paths = [];
			// module.parent = undefined by default
			module.children = [];
			module.webpackPolyfill = 1;
		}
		return module;
	}


/***/ }),
/* 21 */
/***/ (function(module, exports, __webpack_require__) {

	"use strict";

	exports.__esModule = true;

	var _repeat = __webpack_require__(69);

	var _repeat2 = _interopRequireDefault(_repeat);

	var _last = __webpack_require__(68);

	var _last2 = _interopRequireDefault(_last);

	function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }

	function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

	var INDENT_TYPE_TOP_LEVEL = "top-level";
	var INDENT_TYPE_BLOCK_LEVEL = "block-level";

	/**
	 * Manages indentation levels.
	 *
	 * There are two types of indentation levels:
	 *
	 * - BLOCK_LEVEL : increased by open-parenthesis
	 * - TOP_LEVEL : increased by RESERVED_TOPLEVEL words
	 */

	var Indentation = function () {
	    /**
	     * @param {String} indent Indent value, default is "  " (2 spaces)
	     */
	    function Indentation(indent) {
	        _classCallCheck(this, Indentation);

	        this.indent = indent || "  ";
	        this.indentTypes = [];
	    }

	    /**
	     * Returns current indentation string.
	     * @return {String}
	     */


	    Indentation.prototype.getIndent = function getIndent() {
	        return (0, _repeat2["default"])(this.indent, this.indentTypes.length);
	    };

	    /**
	     * Increases indentation by one top-level indent.
	     */


	    Indentation.prototype.increaseToplevel = function increaseToplevel() {
	        this.indentTypes.push(INDENT_TYPE_TOP_LEVEL);
	    };

	    /**
	     * Increases indentation by one block-level indent.
	     */


	    Indentation.prototype.increaseBlockLevel = function increaseBlockLevel() {
	        this.indentTypes.push(INDENT_TYPE_BLOCK_LEVEL);
	    };

	    /**
	     * Decreases indentation by one top-level indent.
	     * Does nothing when the previous indent is not top-level.
	     */


	    Indentation.prototype.decreaseTopLevel = function decreaseTopLevel() {
	        if ((0, _last2["default"])(this.indentTypes) === INDENT_TYPE_TOP_LEVEL) {
	            this.indentTypes.pop();
	        }
	    };

	    /**
	     * Decreases indentation by one block-level indent.
	     * If there are top-level indents within the block-level indent,
	     * throws away these as well.
	     */


	    Indentation.prototype.decreaseBlockLevel = function decreaseBlockLevel() {
	        while (this.indentTypes.length > 0) {
	            var type = this.indentTypes.pop();
	            if (type !== INDENT_TYPE_TOP_LEVEL) {
	                break;
	            }
	        }
	    };

	    return Indentation;
	}();

	exports["default"] = Indentation;
	module.exports = exports["default"];

/***/ }),
/* 22 */
/***/ (function(module, exports, __webpack_require__) {

	"use strict";

	exports.__esModule = true;

	var _tokenTypes = __webpack_require__(8);

	var _tokenTypes2 = _interopRequireDefault(_tokenTypes);

	function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }

	function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

	var INLINE_MAX_LENGTH = 50;

	/**
	 * Bookkeeper for inline blocks.
	 *
	 * Inline blocks are parenthized expressions that are shorter than INLINE_MAX_LENGTH.
	 * These blocks are formatted on a single line, unlike longer parenthized
	 * expressions where open-parenthesis causes newline and increase of indentation.
	 */

	var InlineBlock = function () {
	    function InlineBlock() {
	        _classCallCheck(this, InlineBlock);

	        this.level = 0;
	    }

	    /**
	     * Begins inline block when lookahead through upcoming tokens determines
	     * that the block would be smaller than INLINE_MAX_LENGTH.
	     * @param  {Object[]} tokens Array of all tokens
	     * @param  {Number} index Current token position
	     */


	    InlineBlock.prototype.beginIfPossible = function beginIfPossible(tokens, index) {
	        if (this.level === 0 && this.isInlineBlock(tokens, index)) {
	            this.level = 1;
	        } else if (this.level > 0) {
	            this.level++;
	        } else {
	            this.level = 0;
	        }
	    };

	    /**
	     * Finishes current inline block.
	     * There might be several nested ones.
	     */


	    InlineBlock.prototype.end = function end() {
	        this.level--;
	    };

	    /**
	     * True when inside an inline block
	     * @return {Boolean}
	     */


	    InlineBlock.prototype.isActive = function isActive() {
	        return this.level > 0;
	    };

	    // Check if this should be an inline parentheses block
	    // Examples are "NOW()", "COUNT(*)", "int(10)", key(`somecolumn`), DECIMAL(7,2)


	    InlineBlock.prototype.isInlineBlock = function isInlineBlock(tokens, index) {
	        var length = 0;
	        var level = 0;

	        for (var i = index; i < tokens.length; i++) {
	            var token = tokens[i];
	            length += token.value.length;

	            // Overran max length
	            if (length > INLINE_MAX_LENGTH) {
	                return false;
	            }

	            if (token.type === _tokenTypes2["default"].OPEN_PAREN) {
	                level++;
	            } else if (token.type === _tokenTypes2["default"].CLOSE_PAREN) {
	                level--;
	                if (level === 0) {
	                    return true;
	                }
	            }

	            if (this.isForbiddenToken(token)) {
	                return false;
	            }
	        }
	        return false;
	    };

	    // Reserved words that cause newlines, comments and semicolons
	    // are not allowed inside inline parentheses block


	    InlineBlock.prototype.isForbiddenToken = function isForbiddenToken(_ref) {
	        var type = _ref.type,
	            value = _ref.value;

	        return type === _tokenTypes2["default"].RESERVED_TOPLEVEL || type === _tokenTypes2["default"].RESERVED_NEWLINE || type === _tokenTypes2["default"].COMMENT || type === _tokenTypes2["default"].BLOCK_COMMENT || value === ";";
	    };

	    return InlineBlock;
	}();

	exports["default"] = InlineBlock;
	module.exports = exports["default"];

/***/ }),
/* 23 */
/***/ (function(module, exports) {

	"use strict";

	exports.__esModule = true;

	function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

	/**
	 * Handles placeholder replacement with given params.
	 */
	var Params = function () {
	    /**
	     * @param {Object} params
	     */
	    function Params(params) {
	        _classCallCheck(this, Params);

	        this.params = params;
	        this.index = 0;
	    }

	    /**
	     * Returns param value that matches given placeholder with param key.
	     * @param {Object} token
	     *   @param {String} token.key Placeholder key
	     *   @param {String} token.value Placeholder value
	     * @return {String} param or token.value when params are missing
	     */


	    Params.prototype.get = function get(_ref) {
	        var key = _ref.key,
	            value = _ref.value;

	        if (!this.params) {
	            return value;
	        }
	        if (key) {
	            return this.params[key];
	        }
	        return this.params[this.index++];
	    };

	    return Params;
	}();

	exports["default"] = Params;
	module.exports = exports["default"];

/***/ }),
/* 24 */
/***/ (function(module, exports, __webpack_require__) {

	"use strict";

	exports.__esModule = true;

	var _Formatter = __webpack_require__(4);

	var _Formatter2 = _interopRequireDefault(_Formatter);

	var _Tokenizer = __webpack_require__(5);

	var _Tokenizer2 = _interopRequireDefault(_Tokenizer);

	function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }

	function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

	var reservedWords = ["ABS", "ACTIVATE", "ALIAS", "ALL", "ALLOCATE", "ALLOW", "ALTER", "ANY", "ARE", "ARRAY", "AS", "ASC", "ASENSITIVE", "ASSOCIATE", "ASUTIME", "ASYMMETRIC", "AT", "ATOMIC", "ATTRIBUTES", "AUDIT", "AUTHORIZATION", "AUX", "AUXILIARY", "AVG", "BEFORE", "BEGIN", "BETWEEN", "BIGINT", "BINARY", "BLOB", "BOOLEAN", "BOTH", "BUFFERPOOL", "BY", "CACHE", "CALL", "CALLED", "CAPTURE", "CARDINALITY", "CASCADED", "CASE", "CAST", "CCSID", "CEIL", "CEILING", "CHAR", "CHARACTER", "CHARACTER_LENGTH", "CHAR_LENGTH", "CHECK", "CLOB", "CLONE", "CLOSE", "CLUSTER", "COALESCE", "COLLATE", "COLLECT", "COLLECTION", "COLLID", "COLUMN", "COMMENT", "COMMIT", "CONCAT", "CONDITION", "CONNECT", "CONNECTION", "CONSTRAINT", "CONTAINS", "CONTINUE", "CONVERT", "CORR", "CORRESPONDING", "COUNT", "COUNT_BIG", "COVAR_POP", "COVAR_SAMP", "CREATE", "CROSS", "CUBE", "CUME_DIST", "CURRENT", "CURRENT_DATE", "CURRENT_DEFAULT_TRANSFORM_GROUP", "CURRENT_LC_CTYPE", "CURRENT_PATH", "CURRENT_ROLE", "CURRENT_SCHEMA", "CURRENT_SERVER", "CURRENT_TIME", "CURRENT_TIMESTAMP", "CURRENT_TIMEZONE", "CURRENT_TRANSFORM_GROUP_FOR_TYPE", "CURRENT_USER", "CURSOR", "CYCLE", "DATA", "DATABASE", "DATAPARTITIONNAME", "DATAPARTITIONNUM", "DATE", "DAY", "DAYS", "DB2GENERAL", "DB2GENRL", "DB2SQL", "DBINFO", "DBPARTITIONNAME", "DBPARTITIONNUM", "DEALLOCATE", "DEC", "DECIMAL", "DECLARE", "DEFAULT", "DEFAULTS", "DEFINITION", "DELETE", "DENSERANK", "DENSE_RANK", "DEREF", "DESCRIBE", "DESCRIPTOR", "DETERMINISTIC", "DIAGNOSTICS", "DISABLE", "DISALLOW", "DISCONNECT", "DISTINCT", "DO", "DOCUMENT", "DOUBLE", "DROP", "DSSIZE", "DYNAMIC", "EACH", "EDITPROC", "ELEMENT", "ELSE", "ELSEIF", "ENABLE", "ENCODING", "ENCRYPTION", "END", "END-EXEC", "ENDING", "ERASE", "ESCAPE", "EVERY", "EXCEPTION", "EXCLUDING", "EXCLUSIVE", "EXEC", "EXECUTE", "EXISTS", "EXIT", "EXP", "EXPLAIN", "EXTENDED", "EXTERNAL", "EXTRACT", "FALSE", "FENCED", "FETCH", "FIELDPROC", "FILE", "FILTER", "FINAL", "FIRST", "FLOAT", "FLOOR", "FOR", "FOREIGN", "FREE", "FULL", "FUNCTION", "FUSION", "GENERAL", "GENERATED", "GET", "GLOBAL", "GOTO", "GRANT", "GRAPHIC", "GROUP", "GROUPING", "HANDLER", "HASH", "HASHED_VALUE", "HINT", "HOLD", "HOUR", "HOURS", "IDENTITY", "IF", "IMMEDIATE", "IN", "INCLUDING", "INCLUSIVE", "INCREMENT", "INDEX", "INDICATOR", "INDICATORS", "INF", "INFINITY", "INHERIT", "INNER", "INOUT", "INSENSITIVE", "INSERT", "INT", "INTEGER", "INTEGRITY", "INTERSECTION", "INTERVAL", "INTO", "IS", "ISOBID", "ISOLATION", "ITERATE", "JAR", "JAVA", "KEEP", "KEY", "LABEL", "LANGUAGE", "LARGE", "LATERAL", "LC_CTYPE", "LEADING", "LEAVE", "LEFT", "LIKE", "LINKTYPE", "LN", "LOCAL", "LOCALDATE", "LOCALE", "LOCALTIME", "LOCALTIMESTAMP", "LOCATOR", "LOCATORS", "LOCK", "LOCKMAX", "LOCKSIZE", "LONG", "LOOP", "LOWER", "MAINTAINED", "MATCH", "MATERIALIZED", "MAX", "MAXVALUE", "MEMBER", "MERGE", "METHOD", "MICROSECOND", "MICROSECONDS", "MIN", "MINUTE", "MINUTES", "MINVALUE", "MOD", "MODE", "MODIFIES", "MODULE", "MONTH", "MONTHS", "MULTISET", "NAN", "NATIONAL", "NATURAL", "NCHAR", "NCLOB", "NEW", "NEW_TABLE", "NEXTVAL", "NO", "NOCACHE", "NOCYCLE", "NODENAME", "NODENUMBER", "NOMAXVALUE", "NOMINVALUE", "NONE", "NOORDER", "NORMALIZE", "NORMALIZED", "NOT", "NULL", "NULLIF", "NULLS", "NUMERIC", "NUMPARTS", "OBID", "OCTET_LENGTH", "OF", "OFFSET", "OLD", "OLD_TABLE", "ON", "ONLY", "OPEN", "OPTIMIZATION", "OPTIMIZE", "OPTION", "ORDER", "OUT", "OUTER", "OVER", "OVERLAPS", "OVERLAY", "OVERRIDING", "PACKAGE", "PADDED", "PAGESIZE", "PARAMETER", "PART", "PARTITION", "PARTITIONED", "PARTITIONING", "PARTITIONS", "PASSWORD", "PATH", "PERCENTILE_CONT", "PERCENTILE_DISC", "PERCENT_RANK", "PIECESIZE", "PLAN", "POSITION", "POWER", "PRECISION", "PREPARE", "PREVVAL", "PRIMARY", "PRIQTY", "PRIVILEGES", "PROCEDURE", "PROGRAM", "PSID", "PUBLIC", "QUERY", "QUERYNO", "RANGE", "RANK", "READ", "READS", "REAL", "RECOVERY", "RECURSIVE", "REF", "REFERENCES", "REFERENCING", "REFRESH", "REGR_AVGX", "REGR_AVGY", "REGR_COUNT", "REGR_INTERCEPT", "REGR_R2", "REGR_SLOPE", "REGR_SXX", "REGR_SXY", "REGR_SYY", "RELEASE", "RENAME", "REPEAT", "RESET", "RESIGNAL", "RESTART", "RESTRICT", "RESULT", "RESULT_SET_LOCATOR", "RETURN", "RETURNS", "REVOKE", "RIGHT", "ROLE", "ROLLBACK", "ROLLUP", "ROUND_CEILING", "ROUND_DOWN", "ROUND_FLOOR", "ROUND_HALF_DOWN", "ROUND_HALF_EVEN", "ROUND_HALF_UP", "ROUND_UP", "ROUTINE", "ROW", "ROWNUMBER", "ROWS", "ROWSET", "ROW_NUMBER", "RRN", "RUN", "SAVEPOINT", "SCHEMA", "SCOPE", "SCRATCHPAD", "SCROLL", "SEARCH", "SECOND", "SECONDS", "SECQTY", "SECURITY", "SENSITIVE", "SEQUENCE", "SESSION", "SESSION_USER", "SIGNAL", "SIMILAR", "SIMPLE", "SMALLINT", "SNAN", "SOME", "SOURCE", "SPECIFIC", "SPECIFICTYPE", "SQL", "SQLEXCEPTION", "SQLID", "SQLSTATE", "SQLWARNING", "SQRT", "STACKED", "STANDARD", "START", "STARTING", "STATEMENT", "STATIC", "STATMENT", "STAY", "STDDEV_POP", "STDDEV_SAMP", "STOGROUP", "STORES", "STYLE", "SUBMULTISET", "SUBSTRING", "SUM", "SUMMARY", "SYMMETRIC", "SYNONYM", "SYSFUN", "SYSIBM", "SYSPROC", "SYSTEM", "SYSTEM_USER", "TABLE", "TABLESAMPLE", "TABLESPACE", "THEN", "TIME", "TIMESTAMP", "TIMEZONE_HOUR", "TIMEZONE_MINUTE", "TO", "TRAILING", "TRANSACTION", "TRANSLATE", "TRANSLATION", "TREAT", "TRIGGER", "TRIM", "TRUE", "TRUNCATE", "TYPE", "UESCAPE", "UNDO", "UNIQUE", "UNKNOWN", "UNNEST", "UNTIL", "UPPER", "USAGE", "USER", "USING", "VALIDPROC", "VALUE", "VARCHAR", "VARIABLE", "VARIANT", "VARYING", "VAR_POP", "VAR_SAMP", "VCAT", "VERSION", "VIEW", "VOLATILE", "VOLUMES", "WHEN", "WHENEVER", "WHILE", "WIDTH_BUCKET", "WINDOW", "WITH", "WITHIN", "WITHOUT", "WLM", "WRITE", "XMLELEMENT", "XMLEXISTS", "XMLNAMESPACES", "YEAR", "YEARS"];

	var reservedToplevelWords = ["ADD", "AFTER", "ALTER COLUMN", "ALTER TABLE", "DELETE FROM", "EXCEPT", "FETCH FIRST", "FROM", "GROUP BY", "GO", "HAVING", "INSERT INTO", "INTERSECT", "LIMIT", "ORDER BY", "SELECT", "SET CURRENT SCHEMA", "SET SCHEMA", "SET", "UNION ALL", "UPDATE", "VALUES", "WHERE"];

	var reservedNewlineWords = ["AND", "CROSS JOIN", "INNER JOIN", "JOIN", "LEFT JOIN", "LEFT OUTER JOIN", "OR", "OUTER JOIN", "RIGHT JOIN", "RIGHT OUTER JOIN"];

	var tokenizer = void 0;

	var Db2Formatter = function () {
	    /**
	     * @param {Object} cfg Different set of configurations
	     */
	    function Db2Formatter(cfg) {
	        _classCallCheck(this, Db2Formatter);

	        this.cfg = cfg;
	    }

	    /**
	     * Formats DB2 query to make it easier to read
	     *
	     * @param {String} query The DB2 query string
	     * @return {String} formatted string
	     */


	    Db2Formatter.prototype.format = function format(query) {
	        if (!tokenizer) {
	            tokenizer = new _Tokenizer2["default"]({
	                reservedWords: reservedWords,
	                reservedToplevelWords: reservedToplevelWords,
	                reservedNewlineWords: reservedNewlineWords,
	                stringTypes: ["\"\"", "''", "``", "[]"],
	                openParens: ["("],
	                closeParens: [")"],
	                indexedPlaceholderTypes: ["?"],
	                namedPlaceholderTypes: [":"],
	                lineCommentTypes: ["--"],
	                specialWordChars: ["#", "@"]
	            });
	        }
	        return new _Formatter2["default"](this.cfg, tokenizer).format(query);
	    };

	    return Db2Formatter;
	}();

	exports["default"] = Db2Formatter;
	module.exports = exports["default"];

/***/ }),
/* 25 */
/***/ (function(module, exports, __webpack_require__) {

	"use strict";

	exports.__esModule = true;

	var _Formatter = __webpack_require__(4);

	var _Formatter2 = _interopRequireDefault(_Formatter);

	var _Tokenizer = __webpack_require__(5);

	var _Tokenizer2 = _interopRequireDefault(_Tokenizer);

	function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }

	function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

	var reservedWords = ["ALL", "ALTER", "ANALYZE", "AND", "ANY", "ARRAY", "AS", "ASC", "BEGIN", "BETWEEN", "BINARY", "BOOLEAN", "BREAK", "BUCKET", "BUILD", "BY", "CALL", "CASE", "CAST", "CLUSTER", "COLLATE", "COLLECTION", "COMMIT", "CONNECT", "CONTINUE", "CORRELATE", "COVER", "CREATE", "DATABASE", "DATASET", "DATASTORE", "DECLARE", "DECREMENT", "DELETE", "DERIVED", "DESC", "DESCRIBE", "DISTINCT", "DO", "DROP", "EACH", "ELEMENT", "ELSE", "END", "EVERY", "EXCEPT", "EXCLUDE", "EXECUTE", "EXISTS", "EXPLAIN", "FALSE", "FETCH", "FIRST", "FLATTEN", "FOR", "FORCE", "FROM", "FUNCTION", "GRANT", "GROUP", "GSI", "HAVING", "IF", "IGNORE", "ILIKE", "IN", "INCLUDE", "INCREMENT", "INDEX", "INFER", "INLINE", "INNER", "INSERT", "INTERSECT", "INTO", "IS", "JOIN", "KEY", "KEYS", "KEYSPACE", "KNOWN", "LAST", "LEFT", "LET", "LETTING", "LIKE", "LIMIT", "LSM", "MAP", "MAPPING", "MATCHED", "MATERIALIZED", "MERGE", "MINUS", "MISSING", "NAMESPACE", "NEST", "NOT", "NULL", "NUMBER", "OBJECT", "OFFSET", "ON", "OPTION", "OR", "ORDER", "OUTER", "OVER", "PARSE", "PARTITION", "PASSWORD", "PATH", "POOL", "PREPARE", "PRIMARY", "PRIVATE", "PRIVILEGE", "PROCEDURE", "PUBLIC", "RAW", "REALM", "REDUCE", "RENAME", "RETURN", "RETURNING", "REVOKE", "RIGHT", "ROLE", "ROLLBACK", "SATISFIES", "SCHEMA", "SELECT", "SELF", "SEMI", "SET", "SHOW", "SOME", "START", "STATISTICS", "STRING", "SYSTEM", "THEN", "TO", "TRANSACTION", "TRIGGER", "TRUE", "TRUNCATE", "UNDER", "UNION", "UNIQUE", "UNKNOWN", "UNNEST", "UNSET", "UPDATE", "UPSERT", "USE", "USER", "USING", "VALIDATE", "VALUE", "VALUED", "VALUES", "VIA", "VIEW", "WHEN", "WHERE", "WHILE", "WITH", "WITHIN", "WORK", "XOR"];

	var reservedToplevelWords = ["DELETE FROM", "EXCEPT ALL", "EXCEPT", "EXPLAIN DELETE FROM", "EXPLAIN UPDATE", "EXPLAIN UPSERT", "FROM", "GROUP BY", "HAVING", "INFER", "INSERT INTO", "INTERSECT ALL", "INTERSECT", "LET", "LIMIT", "MERGE", "NEST", "ORDER BY", "PREPARE", "SELECT", "SET CURRENT SCHEMA", "SET SCHEMA", "SET", "UNION ALL", "UNION", "UNNEST", "UPDATE", "UPSERT", "USE KEYS", "VALUES", "WHERE"];

	var reservedNewlineWords = ["AND", "INNER JOIN", "JOIN", "LEFT JOIN", "LEFT OUTER JOIN", "OR", "OUTER JOIN", "RIGHT JOIN", "RIGHT OUTER JOIN", "XOR"];

	var tokenizer = void 0;

	var N1qlFormatter = function () {
	    /**
	     * @param {Object} cfg Different set of configurations
	     */
	    function N1qlFormatter(cfg) {
	        _classCallCheck(this, N1qlFormatter);

	        this.cfg = cfg;
	    }

	    /**
	     * Format the whitespace in a N1QL string to make it easier to read
	     *
	     * @param {String} query The N1QL string
	     * @return {String} formatted string
	     */


	    N1qlFormatter.prototype.format = function format(query) {
	        if (!tokenizer) {
	            tokenizer = new _Tokenizer2["default"]({
	                reservedWords: reservedWords,
	                reservedToplevelWords: reservedToplevelWords,
	                reservedNewlineWords: reservedNewlineWords,
	                stringTypes: ["\"\"", "''", "``"],
	                openParens: ["(", "[", "{"],
	                closeParens: [")", "]", "}"],
	                namedPlaceholderTypes: ["$"],
	                lineCommentTypes: ["#", "--"]
	            });
	        }
	        return new _Formatter2["default"](this.cfg, tokenizer).format(query);
	    };

	    return N1qlFormatter;
	}();

	exports["default"] = N1qlFormatter;
	module.exports = exports["default"];

/***/ }),
/* 26 */
/***/ (function(module, exports, __webpack_require__) {

	"use strict";

	exports.__esModule = true;

	var _Formatter = __webpack_require__(4);

	var _Formatter2 = _interopRequireDefault(_Formatter);

	var _Tokenizer = __webpack_require__(5);

	var _Tokenizer2 = _interopRequireDefault(_Tokenizer);

	function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }

	function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

	var reservedWords = ["A", "ACCESSIBLE", "AGENT", "AGGREGATE", "ALL", "ALTER", "ANY", "ARRAY", "AS", "ASC", "AT", "ATTRIBUTE", "AUTHID", "AVG", "BETWEEN", "BFILE_BASE", "BINARY_INTEGER", "BINARY", "BLOB_BASE", "BLOCK", "BODY", "BOOLEAN", "BOTH", "BOUND", "BULK", "BY", "BYTE", "C", "CALL", "CALLING", "CASCADE", "CASE", "CHAR_BASE", "CHAR", "CHARACTER", "CHARSET", "CHARSETFORM", "CHARSETID", "CHECK", "CLOB_BASE", "CLONE", "CLOSE", "CLUSTER", "CLUSTERS", "COALESCE", "COLAUTH", "COLLECT", "COLUMNS", "COMMENT", "COMMIT", "COMMITTED", "COMPILED", "COMPRESS", "CONNECT", "CONSTANT", "CONSTRUCTOR", "CONTEXT", "CONTINUE", "CONVERT", "COUNT", "CRASH", "CREATE", "CREDENTIAL", "CURRENT", "CURRVAL", "CURSOR", "CUSTOMDATUM", "DANGLING", "DATA", "DATE_BASE", "DATE", "DAY", "DECIMAL", "DEFAULT", "DEFINE", "DELETE", "DESC", "DETERMINISTIC", "DIRECTORY", "DISTINCT", "DO", "DOUBLE", "DROP", "DURATION", "ELEMENT", "ELSIF", "EMPTY", "ESCAPE", "EXCEPTIONS", "EXCLUSIVE", "EXECUTE", "EXISTS", "EXIT", "EXTENDS", "EXTERNAL", "EXTRACT", "FALSE", "FETCH", "FINAL", "FIRST", "FIXED", "FLOAT", "FOR", "FORALL", "FORCE", "FROM", "FUNCTION", "GENERAL", "GOTO", "GRANT", "GROUP", "HASH", "HEAP", "HIDDEN", "HOUR", "IDENTIFIED", "IF", "IMMEDIATE", "IN", "INCLUDING", "INDEX", "INDEXES", "INDICATOR", "INDICES", "INFINITE", "INSTANTIABLE", "INT", "INTEGER", "INTERFACE", "INTERVAL", "INTO", "INVALIDATE", "IS", "ISOLATION", "JAVA", "LANGUAGE", "LARGE", "LEADING", "LENGTH", "LEVEL", "LIBRARY", "LIKE", "LIKE2", "LIKE4", "LIKEC", "LIMITED", "LOCAL", "LOCK", "LONG", "MAP", "MAX", "MAXLEN", "MEMBER", "MERGE", "MIN", "MINUS", "MINUTE", "MLSLABEL", "MOD", "MODE", "MONTH", "MULTISET", "NAME", "NAN", "NATIONAL", "NATIVE", "NATURAL", "NATURALN", "NCHAR", "NEW", "NEXTVAL", "NOCOMPRESS", "NOCOPY", "NOT", "NOWAIT", "NULL", "NULLIF", "NUMBER_BASE", "NUMBER", "OBJECT", "OCICOLL", "OCIDATE", "OCIDATETIME", "OCIDURATION", "OCIINTERVAL", "OCILOBLOCATOR", "OCINUMBER", "OCIRAW", "OCIREF", "OCIREFCURSOR", "OCIROWID", "OCISTRING", "OCITYPE", "OF", "OLD", "ON", "ONLY", "OPAQUE", "OPEN", "OPERATOR", "OPTION", "ORACLE", "ORADATA", "ORDER", "ORGANIZATION", "ORLANY", "ORLVARY", "OTHERS", "OUT", "OVERLAPS", "OVERRIDING", "PACKAGE", "PARALLEL_ENABLE", "PARAMETER", "PARAMETERS", "PARENT", "PARTITION", "PASCAL", "PCTFREE", "PIPE", "PIPELINED", "PLS_INTEGER", "PLUGGABLE", "POSITIVE", "POSITIVEN", "PRAGMA", "PRECISION", "PRIOR", "PRIVATE", "PROCEDURE", "PUBLIC", "RAISE", "RANGE", "RAW", "READ", "REAL", "RECORD", "REF", "REFERENCE", "RELEASE", "RELIES_ON", "REM", "REMAINDER", "RENAME", "RESOURCE", "RESULT_CACHE", "RESULT", "RETURN", "RETURNING", "REVERSE", "REVOKE", "ROLLBACK", "ROW", "ROWID", "ROWNUM", "ROWTYPE", "SAMPLE", "SAVE", "SAVEPOINT", "SB1", "SB2", "SB4", "SECOND", "SEGMENT", "SELF", "SEPARATE", "SEQUENCE", "SERIALIZABLE", "SHARE", "SHORT", "SIZE_T", "SIZE", "SMALLINT", "SOME", "SPACE", "SPARSE", "SQL", "SQLCODE", "SQLDATA", "SQLERRM", "SQLNAME", "SQLSTATE", "STANDARD", "START", "STATIC", "STDDEV", "STORED", "STRING", "STRUCT", "STYLE", "SUBMULTISET", "SUBPARTITION", "SUBSTITUTABLE", "SUBTYPE", "SUCCESSFUL", "SUM", "SYNONYM", "SYSDATE", "TABAUTH", "TABLE", "TDO", "THE", "THEN", "TIME", "TIMESTAMP", "TIMEZONE_ABBR", "TIMEZONE_HOUR", "TIMEZONE_MINUTE", "TIMEZONE_REGION", "TO", "TRAILING", "TRANSACTION", "TRANSACTIONAL", "TRIGGER", "TRUE", "TRUSTED", "TYPE", "UB1", "UB2", "UB4", "UID", "UNDER", "UNIQUE", "UNPLUG", "UNSIGNED", "UNTRUSTED", "USE", "USER", "USING", "VALIDATE", "VALIST", "VALUE", "VARCHAR", "VARCHAR2", "VARIABLE", "VARIANCE", "VARRAY", "VARYING", "VIEW", "VIEWS", "VOID", "WHENEVER", "WHILE", "WITH", "WORK", "WRAPPED", "WRITE", "YEAR", "ZONE"];

	var reservedToplevelWords = ["ADD", "ALTER COLUMN", "ALTER TABLE", "BEGIN", "CONNECT BY", "DECLARE", "DELETE FROM", "DELETE", "END", "EXCEPT", "EXCEPTION", "FETCH FIRST", "FROM", "GROUP BY", "HAVING", "INSERT INTO", "INSERT", "INTERSECT", "LIMIT", "LOOP", "MODIFY", "ORDER BY", "SELECT", "SET CURRENT SCHEMA", "SET SCHEMA", "SET", "START WITH", "UNION ALL", "UNION", "UPDATE", "VALUES", "WHERE"];

	var reservedNewlineWords = ["AND", "CROSS APPLY", "CROSS JOIN", "ELSE", "END", "INNER JOIN", "JOIN", "LEFT JOIN", "LEFT OUTER JOIN", "OR", "OUTER APPLY", "OUTER JOIN", "RIGHT JOIN", "RIGHT OUTER JOIN", "WHEN", "XOR"];

	var tokenizer = void 0;

	var PlSqlFormatter = function () {
	    /**
	     * @param {Object} cfg Different set of configurations
	     */
	    function PlSqlFormatter(cfg) {
	        _classCallCheck(this, PlSqlFormatter);

	        this.cfg = cfg;
	    }

	    /**
	     * Format the whitespace in a PL/SQL string to make it easier to read
	     *
	     * @param {String} query The PL/SQL string
	     * @return {String} formatted string
	     */


	    PlSqlFormatter.prototype.format = function format(query) {
	        if (!tokenizer) {
	            tokenizer = new _Tokenizer2["default"]({
	                reservedWords: reservedWords,
	                reservedToplevelWords: reservedToplevelWords,
	                reservedNewlineWords: reservedNewlineWords,
	                stringTypes: ["\"\"", "N''", "''", "``"],
	                openParens: ["(", "CASE"],
	                closeParens: [")", "END"],
	                indexedPlaceholderTypes: ["?"],
	                namedPlaceholderTypes: [":"],
	                lineCommentTypes: ["--"],
	                specialWordChars: ["_", "$", "#", ".", "@"]
	            });
	        }
	        return new _Formatter2["default"](this.cfg, tokenizer).format(query);
	    };

	    return PlSqlFormatter;
	}();

	exports["default"] = PlSqlFormatter;
	module.exports = exports["default"];

/***/ }),
/* 27 */
/***/ (function(module, exports, __webpack_require__) {

	"use strict";

	exports.__esModule = true;

	var _Formatter = __webpack_require__(4);

	var _Formatter2 = _interopRequireDefault(_Formatter);

	var _Tokenizer = __webpack_require__(5);

	var _Tokenizer2 = _interopRequireDefault(_Tokenizer);

	function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }

	function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

	var reservedWords = ["ACCESSIBLE", "ACTION", "AGAINST", "AGGREGATE", "ALGORITHM", "ALL", "ALTER", "ANALYSE", "ANALYZE", "AS", "ASC", "AUTOCOMMIT", "AUTO_INCREMENT", "BACKUP", "BEGIN", "BETWEEN", "BINLOG", "BOTH", "CASCADE", "CASE", "CHANGE", "CHANGED", "CHARACTER SET", "CHARSET", "CHECK", "CHECKSUM", "COLLATE", "COLLATION", "COLUMN", "COLUMNS", "COMMENT", "COMMIT", "COMMITTED", "COMPRESSED", "CONCURRENT", "CONSTRAINT", "CONTAINS", "CONVERT", "CREATE", "CROSS", "CURRENT_TIMESTAMP", "DATABASE", "DATABASES", "DAY", "DAY_HOUR", "DAY_MINUTE", "DAY_SECOND", "DEFAULT", "DEFINER", "DELAYED", "DELETE", "DESC", "DESCRIBE", "DETERMINISTIC", "DISTINCT", "DISTINCTROW", "DIV", "DO", "DROP", "DUMPFILE", "DUPLICATE", "DYNAMIC", "ELSE", "ENCLOSED", "END", "ENGINE", "ENGINES", "ENGINE_TYPE", "ESCAPE", "ESCAPED", "EVENTS", "EXEC", "EXECUTE", "EXISTS", "EXPLAIN", "EXTENDED", "FAST", "FETCH", "FIELDS", "FILE", "FIRST", "FIXED", "FLUSH", "FOR", "FORCE", "FOREIGN", "FULL", "FULLTEXT", "FUNCTION", "GLOBAL", "GRANT", "GRANTS", "GROUP_CONCAT", "HEAP", "HIGH_PRIORITY", "HOSTS", "HOUR", "HOUR_MINUTE", "HOUR_SECOND", "IDENTIFIED", "IF", "IFNULL", "IGNORE", "IN", "INDEX", "INDEXES", "INFILE", "INSERT", "INSERT_ID", "INSERT_METHOD", "INTERVAL", "INTO", "INVOKER", "IS", "ISOLATION", "KEY", "KEYS", "KILL", "LAST_INSERT_ID", "LEADING", "LEVEL", "LIKE", "LINEAR", "LINES", "LOAD", "LOCAL", "LOCK", "LOCKS", "LOGS", "LOW_PRIORITY", "MARIA", "MASTER", "MASTER_CONNECT_RETRY", "MASTER_HOST", "MASTER_LOG_FILE", "MATCH", "MAX_CONNECTIONS_PER_HOUR", "MAX_QUERIES_PER_HOUR", "MAX_ROWS", "MAX_UPDATES_PER_HOUR", "MAX_USER_CONNECTIONS", "MEDIUM", "MERGE", "MINUTE", "MINUTE_SECOND", "MIN_ROWS", "MODE", "MODIFY", "MONTH", "MRG_MYISAM", "MYISAM", "NAMES", "NATURAL", "NOT", "NOW()", "NULL", "OFFSET", "ON DELETE", "ON UPDATE", "ON", "ONLY", "OPEN", "OPTIMIZE", "OPTION", "OPTIONALLY", "OUTFILE", "PACK_KEYS", "PAGE", "PARTIAL", "PARTITION", "PARTITIONS", "PASSWORD", "PRIMARY", "PRIVILEGES", "PROCEDURE", "PROCESS", "PROCESSLIST", "PURGE", "QUICK", "RAID0", "RAID_CHUNKS", "RAID_CHUNKSIZE", "RAID_TYPE", "RANGE", "READ", "READ_ONLY", "READ_WRITE", "REFERENCES", "REGEXP", "RELOAD", "RENAME", "REPAIR", "REPEATABLE", "REPLACE", "REPLICATION", "RESET", "RESTORE", "RESTRICT", "RETURN", "RETURNS", "REVOKE", "RLIKE", "ROLLBACK", "ROW", "ROWS", "ROW_FORMAT", "SECOND", "SECURITY", "SEPARATOR", "SERIALIZABLE", "SESSION", "SHARE", "SHOW", "SHUTDOWN", "SLAVE", "SONAME", "SOUNDS", "SQL", "SQL_AUTO_IS_NULL", "SQL_BIG_RESULT", "SQL_BIG_SELECTS", "SQL_BIG_TABLES", "SQL_BUFFER_RESULT", "SQL_CACHE", "SQL_CALC_FOUND_ROWS", "SQL_LOG_BIN", "SQL_LOG_OFF", "SQL_LOG_UPDATE", "SQL_LOW_PRIORITY_UPDATES", "SQL_MAX_JOIN_SIZE", "SQL_NO_CACHE", "SQL_QUOTE_SHOW_CREATE", "SQL_SAFE_UPDATES", "SQL_SELECT_LIMIT", "SQL_SLAVE_SKIP_COUNTER", "SQL_SMALL_RESULT", "SQL_WARNINGS", "START", "STARTING", "STATUS", "STOP", "STORAGE", "STRAIGHT_JOIN", "STRING", "STRIPED", "SUPER", "TABLE", "TABLES", "TEMPORARY", "TERMINATED", "THEN", "TO", "TRAILING", "TRANSACTIONAL", "TRUE", "TRUNCATE", "TYPE", "TYPES", "UNCOMMITTED", "UNIQUE", "UNLOCK", "UNSIGNED", "USAGE", "USE", "USING", "VARIABLES", "VIEW", "WHEN", "WITH", "WORK", "WRITE", "YEAR_MONTH"];

	var reservedToplevelWords = ["ADD", "AFTER", "ALTER COLUMN", "ALTER TABLE", "DELETE FROM", "EXCEPT", "FETCH FIRST", "FROM", "GROUP BY", "GO", "HAVING", "INSERT INTO", "INSERT", "INTERSECT", "LIMIT", "MODIFY", "ORDER BY", "SELECT", "SET CURRENT SCHEMA", "SET SCHEMA", "SET", "UNION ALL", "UNION", "UPDATE", "VALUES", "WHERE"];

	var reservedNewlineWords = ["AND", "CROSS APPLY", "CROSS JOIN", "ELSE", "INNER JOIN", "JOIN", "LEFT JOIN", "LEFT OUTER JOIN", "OR", "OUTER APPLY", "OUTER JOIN", "RIGHT JOIN", "RIGHT OUTER JOIN", "WHEN", "XOR"];

	var tokenizer = void 0;

	var StandardSqlFormatter = function () {
	    /**
	     * @param {Object} cfg Different set of configurations
	     */
	    function StandardSqlFormatter(cfg) {
	        _classCallCheck(this, StandardSqlFormatter);

	        this.cfg = cfg;
	    }

	    /**
	     * Format the whitespace in a Standard SQL string to make it easier to read
	     *
	     * @param {String} query The Standard SQL string
	     * @return {String} formatted string
	     */


	    StandardSqlFormatter.prototype.format = function format(query) {
	        if (!tokenizer) {
	            tokenizer = new _Tokenizer2["default"]({
	                reservedWords: reservedWords,
	                reservedToplevelWords: reservedToplevelWords,
	                reservedNewlineWords: reservedNewlineWords,
	                stringTypes: ["\"\"", "N''", "''", "``", "[]"],
	                openParens: ["(", "CASE"],
	                closeParens: [")", "END"],
	                indexedPlaceholderTypes: ["?"],
	                namedPlaceholderTypes: ["@", ":"],
	                lineCommentTypes: ["#", "--"]
	            });
	        }
	        return new _Formatter2["default"](this.cfg, tokenizer).format(query);
	    };

	    return StandardSqlFormatter;
	}();

	exports["default"] = StandardSqlFormatter;
	module.exports = exports["default"];

/***/ }),
/* 28 */
/***/ (function(module, exports, __webpack_require__) {

	var getNative = __webpack_require__(3),
	    root = __webpack_require__(1);

	/* Built-in method references that are verified to be native. */
	var DataView = getNative(root, 'DataView');

	module.exports = DataView;


/***/ }),
/* 29 */
/***/ (function(module, exports, __webpack_require__) {

	var getNative = __webpack_require__(3),
	    root = __webpack_require__(1);

	/* Built-in method references that are verified to be native. */
	var Map = getNative(root, 'Map');

	module.exports = Map;


/***/ }),
/* 30 */
/***/ (function(module, exports, __webpack_require__) {

	var getNative = __webpack_require__(3),
	    root = __webpack_require__(1);

	/* Built-in method references that are verified to be native. */
	var Promise = getNative(root, 'Promise');

	module.exports = Promise;


/***/ }),
/* 31 */
/***/ (function(module, exports, __webpack_require__) {

	var getNative = __webpack_require__(3),
	    root = __webpack_require__(1);

	/* Built-in method references that are verified to be native. */
	var Set = getNative(root, 'Set');

	module.exports = Set;


/***/ }),
/* 32 */
/***/ (function(module, exports, __webpack_require__) {

	var getNative = __webpack_require__(3),
	    root = __webpack_require__(1);

	/* Built-in method references that are verified to be native. */
	var WeakMap = getNative(root, 'WeakMap');

	module.exports = WeakMap;


/***/ }),
/* 33 */
/***/ (function(module, exports) {

	/**
	 * A specialized version of `_.map` for arrays without support for iteratee
	 * shorthands.
	 *
	 * @private
	 * @param {Array} [array] The array to iterate over.
	 * @param {Function} iteratee The function invoked per iteration.
	 * @returns {Array} Returns the new mapped array.
	 */
	function arrayMap(array, iteratee) {
	  var index = -1,
	      length = array == null ? 0 : array.length,
	      result = Array(length);

	  while (++index < length) {
	    result[index] = iteratee(array[index], index, array);
	  }
	  return result;
	}

	module.exports = arrayMap;


/***/ }),
/* 34 */
/***/ (function(module, exports) {

	/**
	 * Converts an ASCII `string` to an array.
	 *
	 * @private
	 * @param {string} string The string to convert.
	 * @returns {Array} Returns the converted array.
	 */
	function asciiToArray(string) {
	  return string.split('');
	}

	module.exports = asciiToArray;


/***/ }),
/* 35 */
/***/ (function(module, exports) {

	/**
	 * The base implementation of `_.findIndex` and `_.findLastIndex` without
	 * support for iteratee shorthands.
	 *
	 * @private
	 * @param {Array} array The array to inspect.
	 * @param {Function} predicate The function invoked per iteration.
	 * @param {number} fromIndex The index to search from.
	 * @param {boolean} [fromRight] Specify iterating from right to left.
	 * @returns {number} Returns the index of the matched value, else `-1`.
	 */
	function baseFindIndex(array, predicate, fromIndex, fromRight) {
	  var length = array.length,
	      index = fromIndex + (fromRight ? 1 : -1);

	  while ((fromRight ? index-- : ++index < length)) {
	    if (predicate(array[index], index, array)) {
	      return index;
	    }
	  }
	  return -1;
	}

	module.exports = baseFindIndex;


/***/ }),
/* 36 */
/***/ (function(module, exports, __webpack_require__) {

	var baseFindIndex = __webpack_require__(35),
	    baseIsNaN = __webpack_require__(38),
	    strictIndexOf = __webpack_require__(59);

	/**
	 * The base implementation of `_.indexOf` without `fromIndex` bounds checks.
	 *
	 * @private
	 * @param {Array} array The array to inspect.
	 * @param {*} value The value to search for.
	 * @param {number} fromIndex The index to search from.
	 * @returns {number} Returns the index of the matched value, else `-1`.
	 */
	function baseIndexOf(array, value, fromIndex) {
	  return value === value
	    ? strictIndexOf(array, value, fromIndex)
	    : baseFindIndex(array, baseIsNaN, fromIndex);
	}

	module.exports = baseIndexOf;


/***/ }),
/* 37 */
/***/ (function(module, exports, __webpack_require__) {

	var baseGetTag = __webpack_require__(2),
	    isObjectLike = __webpack_require__(7);

	/** `Object#toString` result references. */
	var argsTag = '[object Arguments]';

	/**
	 * The base implementation of `_.isArguments`.
	 *
	 * @private
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is an `arguments` object,
	 */
	function baseIsArguments(value) {
	  return isObjectLike(value) && baseGetTag(value) == argsTag;
	}

	module.exports = baseIsArguments;


/***/ }),
/* 38 */
/***/ (function(module, exports) {

	/**
	 * The base implementation of `_.isNaN` without support for number objects.
	 *
	 * @private
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is `NaN`, else `false`.
	 */
	function baseIsNaN(value) {
	  return value !== value;
	}

	module.exports = baseIsNaN;


/***/ }),
/* 39 */
/***/ (function(module, exports, __webpack_require__) {

	var isFunction = __webpack_require__(17),
	    isMasked = __webpack_require__(54),
	    isObject = __webpack_require__(6),
	    toSource = __webpack_require__(14);

	/**
	 * Used to match `RegExp`
	 * [syntax characters](http://ecma-international.org/ecma-262/7.0/#sec-patterns).
	 */
	var reRegExpChar = /[\\^$.*+?()[\]{}|]/g;

	/** Used to detect host constructors (Safari). */
	var reIsHostCtor = /^\[object .+?Constructor\]$/;

	/** Used for built-in method references. */
	var funcProto = Function.prototype,
	    objectProto = Object.prototype;

	/** Used to resolve the decompiled source of functions. */
	var funcToString = funcProto.toString;

	/** Used to check objects for own properties. */
	var hasOwnProperty = objectProto.hasOwnProperty;

	/** Used to detect if a method is native. */
	var reIsNative = RegExp('^' +
	  funcToString.call(hasOwnProperty).replace(reRegExpChar, '\\$&')
	  .replace(/hasOwnProperty|(function).*?(?=\\\()| for .+?(?=\\\])/g, '$1.*?') + '$'
	);

	/**
	 * The base implementation of `_.isNative` without bad shim checks.
	 *
	 * @private
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is a native function,
	 *  else `false`.
	 */
	function baseIsNative(value) {
	  if (!isObject(value) || isMasked(value)) {
	    return false;
	  }
	  var pattern = isFunction(value) ? reIsNative : reIsHostCtor;
	  return pattern.test(toSource(value));
	}

	module.exports = baseIsNative;


/***/ }),
/* 40 */
/***/ (function(module, exports, __webpack_require__) {

	var baseGetTag = __webpack_require__(2),
	    isLength = __webpack_require__(18),
	    isObjectLike = __webpack_require__(7);

	/** `Object#toString` result references. */
	var argsTag = '[object Arguments]',
	    arrayTag = '[object Array]',
	    boolTag = '[object Boolean]',
	    dateTag = '[object Date]',
	    errorTag = '[object Error]',
	    funcTag = '[object Function]',
	    mapTag = '[object Map]',
	    numberTag = '[object Number]',
	    objectTag = '[object Object]',
	    regexpTag = '[object RegExp]',
	    setTag = '[object Set]',
	    stringTag = '[object String]',
	    weakMapTag = '[object WeakMap]';

	var arrayBufferTag = '[object ArrayBuffer]',
	    dataViewTag = '[object DataView]',
	    float32Tag = '[object Float32Array]',
	    float64Tag = '[object Float64Array]',
	    int8Tag = '[object Int8Array]',
	    int16Tag = '[object Int16Array]',
	    int32Tag = '[object Int32Array]',
	    uint8Tag = '[object Uint8Array]',
	    uint8ClampedTag = '[object Uint8ClampedArray]',
	    uint16Tag = '[object Uint16Array]',
	    uint32Tag = '[object Uint32Array]';

	/** Used to identify `toStringTag` values of typed arrays. */
	var typedArrayTags = {};
	typedArrayTags[float32Tag] = typedArrayTags[float64Tag] =
	typedArrayTags[int8Tag] = typedArrayTags[int16Tag] =
	typedArrayTags[int32Tag] = typedArrayTags[uint8Tag] =
	typedArrayTags[uint8ClampedTag] = typedArrayTags[uint16Tag] =
	typedArrayTags[uint32Tag] = true;
	typedArrayTags[argsTag] = typedArrayTags[arrayTag] =
	typedArrayTags[arrayBufferTag] = typedArrayTags[boolTag] =
	typedArrayTags[dataViewTag] = typedArrayTags[dateTag] =
	typedArrayTags[errorTag] = typedArrayTags[funcTag] =
	typedArrayTags[mapTag] = typedArrayTags[numberTag] =
	typedArrayTags[objectTag] = typedArrayTags[regexpTag] =
	typedArrayTags[setTag] = typedArrayTags[stringTag] =
	typedArrayTags[weakMapTag] = false;

	/**
	 * The base implementation of `_.isTypedArray` without Node.js optimizations.
	 *
	 * @private
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is a typed array, else `false`.
	 */
	function baseIsTypedArray(value) {
	  return isObjectLike(value) &&
	    isLength(value.length) && !!typedArrayTags[baseGetTag(value)];
	}

	module.exports = baseIsTypedArray;


/***/ }),
/* 41 */
/***/ (function(module, exports, __webpack_require__) {

	var isPrototype = __webpack_require__(13),
	    nativeKeys = __webpack_require__(55);

	/** Used for built-in method references. */
	var objectProto = Object.prototype;

	/** Used to check objects for own properties. */
	var hasOwnProperty = objectProto.hasOwnProperty;

	/**
	 * The base implementation of `_.keys` which doesn't treat sparse arrays as dense.
	 *
	 * @private
	 * @param {Object} object The object to query.
	 * @returns {Array} Returns the array of property names.
	 */
	function baseKeys(object) {
	  if (!isPrototype(object)) {
	    return nativeKeys(object);
	  }
	  var result = [];
	  for (var key in Object(object)) {
	    if (hasOwnProperty.call(object, key) && key != 'constructor') {
	      result.push(key);
	    }
	  }
	  return result;
	}

	module.exports = baseKeys;


/***/ }),
/* 42 */
/***/ (function(module, exports) {

	/** Used as references for various `Number` constants. */
	var MAX_SAFE_INTEGER = 9007199254740991;

	/* Built-in method references for those with the same name as other `lodash` methods. */
	var nativeFloor = Math.floor;

	/**
	 * The base implementation of `_.repeat` which doesn't coerce arguments.
	 *
	 * @private
	 * @param {string} string The string to repeat.
	 * @param {number} n The number of times to repeat the string.
	 * @returns {string} Returns the repeated string.
	 */
	function baseRepeat(string, n) {
	  var result = '';
	  if (!string || n < 1 || n > MAX_SAFE_INTEGER) {
	    return result;
	  }
	  // Leverage the exponentiation by squaring algorithm for a faster repeat.
	  // See https://en.wikipedia.org/wiki/Exponentiation_by_squaring for more details.
	  do {
	    if (n % 2) {
	      result += string;
	    }
	    n = nativeFloor(n / 2);
	    if (n) {
	      string += string;
	    }
	  } while (n);

	  return result;
	}

	module.exports = baseRepeat;


/***/ }),
/* 43 */
/***/ (function(module, exports) {

	/**
	 * The base implementation of `_.slice` without an iteratee call guard.
	 *
	 * @private
	 * @param {Array} array The array to slice.
	 * @param {number} [start=0] The start position.
	 * @param {number} [end=array.length] The end position.
	 * @returns {Array} Returns the slice of `array`.
	 */
	function baseSlice(array, start, end) {
	  var index = -1,
	      length = array.length;

	  if (start < 0) {
	    start = -start > length ? 0 : (length + start);
	  }
	  end = end > length ? length : end;
	  if (end < 0) {
	    end += length;
	  }
	  length = start > end ? 0 : ((end - start) >>> 0);
	  start >>>= 0;

	  var result = Array(length);
	  while (++index < length) {
	    result[index] = array[index + start];
	  }
	  return result;
	}

	module.exports = baseSlice;


/***/ }),
/* 44 */
/***/ (function(module, exports) {

	/**
	 * The base implementation of `_.unary` without support for storing metadata.
	 *
	 * @private
	 * @param {Function} func The function to cap arguments for.
	 * @returns {Function} Returns the new capped function.
	 */
	function baseUnary(func) {
	  return function(value) {
	    return func(value);
	  };
	}

	module.exports = baseUnary;


/***/ }),
/* 45 */
/***/ (function(module, exports, __webpack_require__) {

	var baseSlice = __webpack_require__(43);

	/**
	 * Casts `array` to a slice if it's needed.
	 *
	 * @private
	 * @param {Array} array The array to inspect.
	 * @param {number} start The start position.
	 * @param {number} [end=array.length] The end position.
	 * @returns {Array} Returns the cast slice.
	 */
	function castSlice(array, start, end) {
	  var length = array.length;
	  end = end === undefined ? length : end;
	  return (!start && end >= length) ? array : baseSlice(array, start, end);
	}

	module.exports = castSlice;


/***/ }),
/* 46 */
/***/ (function(module, exports, __webpack_require__) {

	var baseIndexOf = __webpack_require__(36);

	/**
	 * Used by `_.trim` and `_.trimEnd` to get the index of the last string symbol
	 * that is not found in the character symbols.
	 *
	 * @private
	 * @param {Array} strSymbols The string symbols to inspect.
	 * @param {Array} chrSymbols The character symbols to find.
	 * @returns {number} Returns the index of the last unmatched string symbol.
	 */
	function charsEndIndex(strSymbols, chrSymbols) {
	  var index = strSymbols.length;

	  while (index-- && baseIndexOf(chrSymbols, strSymbols[index], 0) > -1) {}
	  return index;
	}

	module.exports = charsEndIndex;


/***/ }),
/* 47 */
/***/ (function(module, exports, __webpack_require__) {

	var root = __webpack_require__(1);

	/** Used to detect overreaching core-js shims. */
	var coreJsData = root['__core-js_shared__'];

	module.exports = coreJsData;


/***/ }),
/* 48 */
/***/ (function(module, exports, __webpack_require__) {

	var Symbol = __webpack_require__(9);

	/** Used for built-in method references. */
	var objectProto = Object.prototype;

	/** Used to check objects for own properties. */
	var hasOwnProperty = objectProto.hasOwnProperty;

	/**
	 * Used to resolve the
	 * [`toStringTag`](http://ecma-international.org/ecma-262/7.0/#sec-object.prototype.tostring)
	 * of values.
	 */
	var nativeObjectToString = objectProto.toString;

	/** Built-in value references. */
	var symToStringTag = Symbol ? Symbol.toStringTag : undefined;

	/**
	 * A specialized version of `baseGetTag` which ignores `Symbol.toStringTag` values.
	 *
	 * @private
	 * @param {*} value The value to query.
	 * @returns {string} Returns the raw `toStringTag`.
	 */
	function getRawTag(value) {
	  var isOwn = hasOwnProperty.call(value, symToStringTag),
	      tag = value[symToStringTag];

	  try {
	    value[symToStringTag] = undefined;
	    var unmasked = true;
	  } catch (e) {}

	  var result = nativeObjectToString.call(value);
	  if (unmasked) {
	    if (isOwn) {
	      value[symToStringTag] = tag;
	    } else {
	      delete value[symToStringTag];
	    }
	  }
	  return result;
	}

	module.exports = getRawTag;


/***/ }),
/* 49 */
/***/ (function(module, exports, __webpack_require__) {

	var DataView = __webpack_require__(28),
	    Map = __webpack_require__(29),
	    Promise = __webpack_require__(30),
	    Set = __webpack_require__(31),
	    WeakMap = __webpack_require__(32),
	    baseGetTag = __webpack_require__(2),
	    toSource = __webpack_require__(14);

	/** `Object#toString` result references. */
	var mapTag = '[object Map]',
	    objectTag = '[object Object]',
	    promiseTag = '[object Promise]',
	    setTag = '[object Set]',
	    weakMapTag = '[object WeakMap]';

	var dataViewTag = '[object DataView]';

	/** Used to detect maps, sets, and weakmaps. */
	var dataViewCtorString = toSource(DataView),
	    mapCtorString = toSource(Map),
	    promiseCtorString = toSource(Promise),
	    setCtorString = toSource(Set),
	    weakMapCtorString = toSource(WeakMap);

	/**
	 * Gets the `toStringTag` of `value`.
	 *
	 * @private
	 * @param {*} value The value to query.
	 * @returns {string} Returns the `toStringTag`.
	 */
	var getTag = baseGetTag;

	// Fallback for data views, maps, sets, and weak maps in IE 11 and promises in Node.js < 6.
	if ((DataView && getTag(new DataView(new ArrayBuffer(1))) != dataViewTag) ||
	    (Map && getTag(new Map) != mapTag) ||
	    (Promise && getTag(Promise.resolve()) != promiseTag) ||
	    (Set && getTag(new Set) != setTag) ||
	    (WeakMap && getTag(new WeakMap) != weakMapTag)) {
	  getTag = function(value) {
	    var result = baseGetTag(value),
	        Ctor = result == objectTag ? value.constructor : undefined,
	        ctorString = Ctor ? toSource(Ctor) : '';

	    if (ctorString) {
	      switch (ctorString) {
	        case dataViewCtorString: return dataViewTag;
	        case mapCtorString: return mapTag;
	        case promiseCtorString: return promiseTag;
	        case setCtorString: return setTag;
	        case weakMapCtorString: return weakMapTag;
	      }
	    }
	    return result;
	  };
	}

	module.exports = getTag;


/***/ }),
/* 50 */
/***/ (function(module, exports) {

	/**
	 * Gets the value at `key` of `object`.
	 *
	 * @private
	 * @param {Object} [object] The object to query.
	 * @param {string} key The key of the property to get.
	 * @returns {*} Returns the property value.
	 */
	function getValue(object, key) {
	  return object == null ? undefined : object[key];
	}

	module.exports = getValue;


/***/ }),
/* 51 */
/***/ (function(module, exports) {

	/** Used to compose unicode character classes. */
	var rsAstralRange = '\\ud800-\\udfff',
	    rsComboMarksRange = '\\u0300-\\u036f',
	    reComboHalfMarksRange = '\\ufe20-\\ufe2f',
	    rsComboSymbolsRange = '\\u20d0-\\u20ff',
	    rsComboRange = rsComboMarksRange + reComboHalfMarksRange + rsComboSymbolsRange,
	    rsVarRange = '\\ufe0e\\ufe0f';

	/** Used to compose unicode capture groups. */
	var rsZWJ = '\\u200d';

	/** Used to detect strings with [zero-width joiners or code points from the astral planes](http://eev.ee/blog/2015/09/12/dark-corners-of-unicode/). */
	var reHasUnicode = RegExp('[' + rsZWJ + rsAstralRange  + rsComboRange + rsVarRange + ']');

	/**
	 * Checks if `string` contains Unicode symbols.
	 *
	 * @private
	 * @param {string} string The string to inspect.
	 * @returns {boolean} Returns `true` if a symbol is found, else `false`.
	 */
	function hasUnicode(string) {
	  return reHasUnicode.test(string);
	}

	module.exports = hasUnicode;


/***/ }),
/* 52 */
/***/ (function(module, exports) {

	/** Used as references for various `Number` constants. */
	var MAX_SAFE_INTEGER = 9007199254740991;

	/** Used to detect unsigned integer values. */
	var reIsUint = /^(?:0|[1-9]\d*)$/;

	/**
	 * Checks if `value` is a valid array-like index.
	 *
	 * @private
	 * @param {*} value The value to check.
	 * @param {number} [length=MAX_SAFE_INTEGER] The upper bounds of a valid index.
	 * @returns {boolean} Returns `true` if `value` is a valid index, else `false`.
	 */
	function isIndex(value, length) {
	  var type = typeof value;
	  length = length == null ? MAX_SAFE_INTEGER : length;

	  return !!length &&
	    (type == 'number' ||
	      (type != 'symbol' && reIsUint.test(value))) &&
	        (value > -1 && value % 1 == 0 && value < length);
	}

	module.exports = isIndex;


/***/ }),
/* 53 */
/***/ (function(module, exports, __webpack_require__) {

	var eq = __webpack_require__(62),
	    isArrayLike = __webpack_require__(16),
	    isIndex = __webpack_require__(52),
	    isObject = __webpack_require__(6);

	/**
	 * Checks if the given arguments are from an iteratee call.
	 *
	 * @private
	 * @param {*} value The potential iteratee value argument.
	 * @param {*} index The potential iteratee index or key argument.
	 * @param {*} object The potential iteratee object argument.
	 * @returns {boolean} Returns `true` if the arguments are from an iteratee call,
	 *  else `false`.
	 */
	function isIterateeCall(value, index, object) {
	  if (!isObject(object)) {
	    return false;
	  }
	  var type = typeof index;
	  if (type == 'number'
	        ? (isArrayLike(object) && isIndex(index, object.length))
	        : (type == 'string' && index in object)
	      ) {
	    return eq(object[index], value);
	  }
	  return false;
	}

	module.exports = isIterateeCall;


/***/ }),
/* 54 */
/***/ (function(module, exports, __webpack_require__) {

	var coreJsData = __webpack_require__(47);

	/** Used to detect methods masquerading as native. */
	var maskSrcKey = (function() {
	  var uid = /[^.]+$/.exec(coreJsData && coreJsData.keys && coreJsData.keys.IE_PROTO || '');
	  return uid ? ('Symbol(src)_1.' + uid) : '';
	}());

	/**
	 * Checks if `func` has its source masked.
	 *
	 * @private
	 * @param {Function} func The function to check.
	 * @returns {boolean} Returns `true` if `func` is masked, else `false`.
	 */
	function isMasked(func) {
	  return !!maskSrcKey && (maskSrcKey in func);
	}

	module.exports = isMasked;


/***/ }),
/* 55 */
/***/ (function(module, exports, __webpack_require__) {

	var overArg = __webpack_require__(58);

	/* Built-in method references for those with the same name as other `lodash` methods. */
	var nativeKeys = overArg(Object.keys, Object);

	module.exports = nativeKeys;


/***/ }),
/* 56 */
/***/ (function(module, exports, __webpack_require__) {

	/* WEBPACK VAR INJECTION */(function(module) {var freeGlobal = __webpack_require__(12);

	/** Detect free variable `exports`. */
	var freeExports = typeof exports == 'object' && exports && !exports.nodeType && exports;

	/** Detect free variable `module`. */
	var freeModule = freeExports && typeof module == 'object' && module && !module.nodeType && module;

	/** Detect the popular CommonJS extension `module.exports`. */
	var moduleExports = freeModule && freeModule.exports === freeExports;

	/** Detect free variable `process` from Node.js. */
	var freeProcess = moduleExports && freeGlobal.process;

	/** Used to access faster Node.js helpers. */
	var nodeUtil = (function() {
	  try {
	    // Use `util.types` for Node.js 10+.
	    var types = freeModule && freeModule.require && freeModule.require('util').types;

	    if (types) {
	      return types;
	    }

	    // Legacy `process.binding('util')` for Node.js < 10.
	    return freeProcess && freeProcess.binding && freeProcess.binding('util');
	  } catch (e) {}
	}());

	module.exports = nodeUtil;

	/* WEBPACK VAR INJECTION */}.call(exports, __webpack_require__(20)(module)))

/***/ }),
/* 57 */
/***/ (function(module, exports) {

	/** Used for built-in method references. */
	var objectProto = Object.prototype;

	/**
	 * Used to resolve the
	 * [`toStringTag`](http://ecma-international.org/ecma-262/7.0/#sec-object.prototype.tostring)
	 * of values.
	 */
	var nativeObjectToString = objectProto.toString;

	/**
	 * Converts `value` to a string using `Object.prototype.toString`.
	 *
	 * @private
	 * @param {*} value The value to convert.
	 * @returns {string} Returns the converted string.
	 */
	function objectToString(value) {
	  return nativeObjectToString.call(value);
	}

	module.exports = objectToString;


/***/ }),
/* 58 */
/***/ (function(module, exports) {

	/**
	 * Creates a unary function that invokes `func` with its argument transformed.
	 *
	 * @private
	 * @param {Function} func The function to wrap.
	 * @param {Function} transform The argument transform.
	 * @returns {Function} Returns the new function.
	 */
	function overArg(func, transform) {
	  return function(arg) {
	    return func(transform(arg));
	  };
	}

	module.exports = overArg;


/***/ }),
/* 59 */
/***/ (function(module, exports) {

	/**
	 * A specialized version of `_.indexOf` which performs strict equality
	 * comparisons of values, i.e. `===`.
	 *
	 * @private
	 * @param {Array} array The array to inspect.
	 * @param {*} value The value to search for.
	 * @param {number} fromIndex The index to search from.
	 * @returns {number} Returns the index of the matched value, else `-1`.
	 */
	function strictIndexOf(array, value, fromIndex) {
	  var index = fromIndex - 1,
	      length = array.length;

	  while (++index < length) {
	    if (array[index] === value) {
	      return index;
	    }
	  }
	  return -1;
	}

	module.exports = strictIndexOf;


/***/ }),
/* 60 */
/***/ (function(module, exports, __webpack_require__) {

	var asciiToArray = __webpack_require__(34),
	    hasUnicode = __webpack_require__(51),
	    unicodeToArray = __webpack_require__(61);

	/**
	 * Converts `string` to an array.
	 *
	 * @private
	 * @param {string} string The string to convert.
	 * @returns {Array} Returns the converted array.
	 */
	function stringToArray(string) {
	  return hasUnicode(string)
	    ? unicodeToArray(string)
	    : asciiToArray(string);
	}

	module.exports = stringToArray;


/***/ }),
/* 61 */
/***/ (function(module, exports) {

	/** Used to compose unicode character classes. */
	var rsAstralRange = '\\ud800-\\udfff',
	    rsComboMarksRange = '\\u0300-\\u036f',
	    reComboHalfMarksRange = '\\ufe20-\\ufe2f',
	    rsComboSymbolsRange = '\\u20d0-\\u20ff',
	    rsComboRange = rsComboMarksRange + reComboHalfMarksRange + rsComboSymbolsRange,
	    rsVarRange = '\\ufe0e\\ufe0f';

	/** Used to compose unicode capture groups. */
	var rsAstral = '[' + rsAstralRange + ']',
	    rsCombo = '[' + rsComboRange + ']',
	    rsFitz = '\\ud83c[\\udffb-\\udfff]',
	    rsModifier = '(?:' + rsCombo + '|' + rsFitz + ')',
	    rsNonAstral = '[^' + rsAstralRange + ']',
	    rsRegional = '(?:\\ud83c[\\udde6-\\uddff]){2}',
	    rsSurrPair = '[\\ud800-\\udbff][\\udc00-\\udfff]',
	    rsZWJ = '\\u200d';

	/** Used to compose unicode regexes. */
	var reOptMod = rsModifier + '?',
	    rsOptVar = '[' + rsVarRange + ']?',
	    rsOptJoin = '(?:' + rsZWJ + '(?:' + [rsNonAstral, rsRegional, rsSurrPair].join('|') + ')' + rsOptVar + reOptMod + ')*',
	    rsSeq = rsOptVar + reOptMod + rsOptJoin,
	    rsSymbol = '(?:' + [rsNonAstral + rsCombo + '?', rsCombo, rsRegional, rsSurrPair, rsAstral].join('|') + ')';

	/** Used to match [string symbols](https://mathiasbynens.be/notes/javascript-unicode). */
	var reUnicode = RegExp(rsFitz + '(?=' + rsFitz + ')|' + rsSymbol + rsSeq, 'g');

	/**
	 * Converts a Unicode `string` to an array.
	 *
	 * @private
	 * @param {string} string The string to convert.
	 * @returns {Array} Returns the converted array.
	 */
	function unicodeToArray(string) {
	  return string.match(reUnicode) || [];
	}

	module.exports = unicodeToArray;


/***/ }),
/* 62 */
/***/ (function(module, exports) {

	/**
	 * Performs a
	 * [`SameValueZero`](http://ecma-international.org/ecma-262/7.0/#sec-samevaluezero)
	 * comparison between two values to determine if they are equivalent.
	 *
	 * @static
	 * @memberOf _
	 * @since 4.0.0
	 * @category Lang
	 * @param {*} value The value to compare.
	 * @param {*} other The other value to compare.
	 * @returns {boolean} Returns `true` if the values are equivalent, else `false`.
	 * @example
	 *
	 * var object = { 'a': 1 };
	 * var other = { 'a': 1 };
	 *
	 * _.eq(object, object);
	 * // => true
	 *
	 * _.eq(object, other);
	 * // => false
	 *
	 * _.eq('a', 'a');
	 * // => true
	 *
	 * _.eq('a', Object('a'));
	 * // => false
	 *
	 * _.eq(NaN, NaN);
	 * // => true
	 */
	function eq(value, other) {
	  return value === other || (value !== value && other !== other);
	}

	module.exports = eq;


/***/ }),
/* 63 */
/***/ (function(module, exports, __webpack_require__) {

	var toString = __webpack_require__(10);

	/**
	 * Used to match `RegExp`
	 * [syntax characters](http://ecma-international.org/ecma-262/7.0/#sec-patterns).
	 */
	var reRegExpChar = /[\\^$.*+?()[\]{}|]/g,
	    reHasRegExpChar = RegExp(reRegExpChar.source);

	/**
	 * Escapes the `RegExp` special characters "^", "$", "\", ".", "*", "+",
	 * "?", "(", ")", "[", "]", "{", "}", and "|" in `string`.
	 *
	 * @static
	 * @memberOf _
	 * @since 3.0.0
	 * @category String
	 * @param {string} [string=''] The string to escape.
	 * @returns {string} Returns the escaped string.
	 * @example
	 *
	 * _.escapeRegExp('[lodash](https://lodash.com/)');
	 * // => '\[lodash\]\(https://lodash\.com/\)'
	 */
	function escapeRegExp(string) {
	  string = toString(string);
	  return (string && reHasRegExpChar.test(string))
	    ? string.replace(reRegExpChar, '\\$&')
	    : string;
	}

	module.exports = escapeRegExp;


/***/ }),
/* 64 */
/***/ (function(module, exports, __webpack_require__) {

	var baseIsArguments = __webpack_require__(37),
	    isObjectLike = __webpack_require__(7);

	/** Used for built-in method references. */
	var objectProto = Object.prototype;

	/** Used to check objects for own properties. */
	var hasOwnProperty = objectProto.hasOwnProperty;

	/** Built-in value references. */
	var propertyIsEnumerable = objectProto.propertyIsEnumerable;

	/**
	 * Checks if `value` is likely an `arguments` object.
	 *
	 * @static
	 * @memberOf _
	 * @since 0.1.0
	 * @category Lang
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is an `arguments` object,
	 *  else `false`.
	 * @example
	 *
	 * _.isArguments(function() { return arguments; }());
	 * // => true
	 *
	 * _.isArguments([1, 2, 3]);
	 * // => false
	 */
	var isArguments = baseIsArguments(function() { return arguments; }()) ? baseIsArguments : function(value) {
	  return isObjectLike(value) && hasOwnProperty.call(value, 'callee') &&
	    !propertyIsEnumerable.call(value, 'callee');
	};

	module.exports = isArguments;


/***/ }),
/* 65 */
/***/ (function(module, exports, __webpack_require__) {

	/* WEBPACK VAR INJECTION */(function(module) {var root = __webpack_require__(1),
	    stubFalse = __webpack_require__(70);

	/** Detect free variable `exports`. */
	var freeExports = typeof exports == 'object' && exports && !exports.nodeType && exports;

	/** Detect free variable `module`. */
	var freeModule = freeExports && typeof module == 'object' && module && !module.nodeType && module;

	/** Detect the popular CommonJS extension `module.exports`. */
	var moduleExports = freeModule && freeModule.exports === freeExports;

	/** Built-in value references. */
	var Buffer = moduleExports ? root.Buffer : undefined;

	/* Built-in method references for those with the same name as other `lodash` methods. */
	var nativeIsBuffer = Buffer ? Buffer.isBuffer : undefined;

	/**
	 * Checks if `value` is a buffer.
	 *
	 * @static
	 * @memberOf _
	 * @since 4.3.0
	 * @category Lang
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is a buffer, else `false`.
	 * @example
	 *
	 * _.isBuffer(new Buffer(2));
	 * // => true
	 *
	 * _.isBuffer(new Uint8Array(2));
	 * // => false
	 */
	var isBuffer = nativeIsBuffer || stubFalse;

	module.exports = isBuffer;

	/* WEBPACK VAR INJECTION */}.call(exports, __webpack_require__(20)(module)))

/***/ }),
/* 66 */
/***/ (function(module, exports, __webpack_require__) {

	var baseKeys = __webpack_require__(41),
	    getTag = __webpack_require__(49),
	    isArguments = __webpack_require__(64),
	    isArray = __webpack_require__(15),
	    isArrayLike = __webpack_require__(16),
	    isBuffer = __webpack_require__(65),
	    isPrototype = __webpack_require__(13),
	    isTypedArray = __webpack_require__(67);

	/** `Object#toString` result references. */
	var mapTag = '[object Map]',
	    setTag = '[object Set]';

	/** Used for built-in method references. */
	var objectProto = Object.prototype;

	/** Used to check objects for own properties. */
	var hasOwnProperty = objectProto.hasOwnProperty;

	/**
	 * Checks if `value` is an empty object, collection, map, or set.
	 *
	 * Objects are considered empty if they have no own enumerable string keyed
	 * properties.
	 *
	 * Array-like values such as `arguments` objects, arrays, buffers, strings, or
	 * jQuery-like collections are considered empty if they have a `length` of `0`.
	 * Similarly, maps and sets are considered empty if they have a `size` of `0`.
	 *
	 * @static
	 * @memberOf _
	 * @since 0.1.0
	 * @category Lang
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is empty, else `false`.
	 * @example
	 *
	 * _.isEmpty(null);
	 * // => true
	 *
	 * _.isEmpty(true);
	 * // => true
	 *
	 * _.isEmpty(1);
	 * // => true
	 *
	 * _.isEmpty([1, 2, 3]);
	 * // => false
	 *
	 * _.isEmpty({ 'a': 1 });
	 * // => false
	 */
	function isEmpty(value) {
	  if (value == null) {
	    return true;
	  }
	  if (isArrayLike(value) &&
	      (isArray(value) || typeof value == 'string' || typeof value.splice == 'function' ||
	        isBuffer(value) || isTypedArray(value) || isArguments(value))) {
	    return !value.length;
	  }
	  var tag = getTag(value);
	  if (tag == mapTag || tag == setTag) {
	    return !value.size;
	  }
	  if (isPrototype(value)) {
	    return !baseKeys(value).length;
	  }
	  for (var key in value) {
	    if (hasOwnProperty.call(value, key)) {
	      return false;
	    }
	  }
	  return true;
	}

	module.exports = isEmpty;


/***/ }),
/* 67 */
/***/ (function(module, exports, __webpack_require__) {

	var baseIsTypedArray = __webpack_require__(40),
	    baseUnary = __webpack_require__(44),
	    nodeUtil = __webpack_require__(56);

	/* Node.js helper references. */
	var nodeIsTypedArray = nodeUtil && nodeUtil.isTypedArray;

	/**
	 * Checks if `value` is classified as a typed array.
	 *
	 * @static
	 * @memberOf _
	 * @since 3.0.0
	 * @category Lang
	 * @param {*} value The value to check.
	 * @returns {boolean} Returns `true` if `value` is a typed array, else `false`.
	 * @example
	 *
	 * _.isTypedArray(new Uint8Array);
	 * // => true
	 *
	 * _.isTypedArray([]);
	 * // => false
	 */
	var isTypedArray = nodeIsTypedArray ? baseUnary(nodeIsTypedArray) : baseIsTypedArray;

	module.exports = isTypedArray;


/***/ }),
/* 68 */
/***/ (function(module, exports) {

	/**
	 * Gets the last element of `array`.
	 *
	 * @static
	 * @memberOf _
	 * @since 0.1.0
	 * @category Array
	 * @param {Array} array The array to query.
	 * @returns {*} Returns the last element of `array`.
	 * @example
	 *
	 * _.last([1, 2, 3]);
	 * // => 3
	 */
	function last(array) {
	  var length = array == null ? 0 : array.length;
	  return length ? array[length - 1] : undefined;
	}

	module.exports = last;


/***/ }),
/* 69 */
/***/ (function(module, exports, __webpack_require__) {

	var baseRepeat = __webpack_require__(42),
	    isIterateeCall = __webpack_require__(53),
	    toInteger = __webpack_require__(72),
	    toString = __webpack_require__(10);

	/**
	 * Repeats the given string `n` times.
	 *
	 * @static
	 * @memberOf _
	 * @since 3.0.0
	 * @category String
	 * @param {string} [string=''] The string to repeat.
	 * @param {number} [n=1] The number of times to repeat the string.
	 * @param- {Object} [guard] Enables use as an iteratee for methods like `_.map`.
	 * @returns {string} Returns the repeated string.
	 * @example
	 *
	 * _.repeat('*', 3);
	 * // => '***'
	 *
	 * _.repeat('abc', 2);
	 * // => 'abcabc'
	 *
	 * _.repeat('abc', 0);
	 * // => ''
	 */
	function repeat(string, n, guard) {
	  if ((guard ? isIterateeCall(string, n, guard) : n === undefined)) {
	    n = 1;
	  } else {
	    n = toInteger(n);
	  }
	  return baseRepeat(toString(string), n);
	}

	module.exports = repeat;


/***/ }),
/* 70 */
/***/ (function(module, exports) {

	/**
	 * This method returns `false`.
	 *
	 * @static
	 * @memberOf _
	 * @since 4.13.0
	 * @category Util
	 * @returns {boolean} Returns `false`.
	 * @example
	 *
	 * _.times(2, _.stubFalse);
	 * // => [false, false]
	 */
	function stubFalse() {
	  return false;
	}

	module.exports = stubFalse;


/***/ }),
/* 71 */
/***/ (function(module, exports, __webpack_require__) {

	var toNumber = __webpack_require__(73);

	/** Used as references for various `Number` constants. */
	var INFINITY = 1 / 0,
	    MAX_INTEGER = 1.7976931348623157e+308;

	/**
	 * Converts `value` to a finite number.
	 *
	 * @static
	 * @memberOf _
	 * @since 4.12.0
	 * @category Lang
	 * @param {*} value The value to convert.
	 * @returns {number} Returns the converted number.
	 * @example
	 *
	 * _.toFinite(3.2);
	 * // => 3.2
	 *
	 * _.toFinite(Number.MIN_VALUE);
	 * // => 5e-324
	 *
	 * _.toFinite(Infinity);
	 * // => 1.7976931348623157e+308
	 *
	 * _.toFinite('3.2');
	 * // => 3.2
	 */
	function toFinite(value) {
	  if (!value) {
	    return value === 0 ? value : 0;
	  }
	  value = toNumber(value);
	  if (value === INFINITY || value === -INFINITY) {
	    var sign = (value < 0 ? -1 : 1);
	    return sign * MAX_INTEGER;
	  }
	  return value === value ? value : 0;
	}

	module.exports = toFinite;


/***/ }),
/* 72 */
/***/ (function(module, exports, __webpack_require__) {

	var toFinite = __webpack_require__(71);

	/**
	 * Converts `value` to an integer.
	 *
	 * **Note:** This method is loosely based on
	 * [`ToInteger`](http://www.ecma-international.org/ecma-262/7.0/#sec-tointeger).
	 *
	 * @static
	 * @memberOf _
	 * @since 4.0.0
	 * @category Lang
	 * @param {*} value The value to convert.
	 * @returns {number} Returns the converted integer.
	 * @example
	 *
	 * _.toInteger(3.2);
	 * // => 3
	 *
	 * _.toInteger(Number.MIN_VALUE);
	 * // => 0
	 *
	 * _.toInteger(Infinity);
	 * // => 1.7976931348623157e+308
	 *
	 * _.toInteger('3.2');
	 * // => 3
	 */
	function toInteger(value) {
	  var result = toFinite(value),
	      remainder = result % 1;

	  return result === result ? (remainder ? result - remainder : result) : 0;
	}

	module.exports = toInteger;


/***/ }),
/* 73 */
/***/ (function(module, exports, __webpack_require__) {

	var isObject = __webpack_require__(6),
	    isSymbol = __webpack_require__(19);

	/** Used as references for various `Number` constants. */
	var NAN = 0 / 0;

	/** Used to match leading and trailing whitespace. */
	var reTrim = /^\s+|\s+$/g;

	/** Used to detect bad signed hexadecimal string values. */
	var reIsBadHex = /^[-+]0x[0-9a-f]+$/i;

	/** Used to detect binary string values. */
	var reIsBinary = /^0b[01]+$/i;

	/** Used to detect octal string values. */
	var reIsOctal = /^0o[0-7]+$/i;

	/** Built-in method references without a dependency on `root`. */
	var freeParseInt = parseInt;

	/**
	 * Converts `value` to a number.
	 *
	 * @static
	 * @memberOf _
	 * @since 4.0.0
	 * @category Lang
	 * @param {*} value The value to process.
	 * @returns {number} Returns the number.
	 * @example
	 *
	 * _.toNumber(3.2);
	 * // => 3.2
	 *
	 * _.toNumber(Number.MIN_VALUE);
	 * // => 5e-324
	 *
	 * _.toNumber(Infinity);
	 * // => Infinity
	 *
	 * _.toNumber('3.2');
	 * // => 3.2
	 */
	function toNumber(value) {
	  if (typeof value == 'number') {
	    return value;
	  }
	  if (isSymbol(value)) {
	    return NAN;
	  }
	  if (isObject(value)) {
	    var other = typeof value.valueOf == 'function' ? value.valueOf() : value;
	    value = isObject(other) ? (other + '') : other;
	  }
	  if (typeof value != 'string') {
	    return value === 0 ? value : +value;
	  }
	  value = value.replace(reTrim, '');
	  var isBinary = reIsBinary.test(value);
	  return (isBinary || reIsOctal.test(value))
	    ? freeParseInt(value.slice(2), isBinary ? 2 : 8)
	    : (reIsBadHex.test(value) ? NAN : +value);
	}

	module.exports = toNumber;


/***/ }),
/* 74 */
/***/ (function(module, exports, __webpack_require__) {

	var baseToString = __webpack_require__(11),
	    castSlice = __webpack_require__(45),
	    charsEndIndex = __webpack_require__(46),
	    stringToArray = __webpack_require__(60),
	    toString = __webpack_require__(10);

	/** Used to match leading and trailing whitespace. */
	var reTrimEnd = /\s+$/;

	/**
	 * Removes trailing whitespace or specified characters from `string`.
	 *
	 * @static
	 * @memberOf _
	 * @since 4.0.0
	 * @category String
	 * @param {string} [string=''] The string to trim.
	 * @param {string} [chars=whitespace] The characters to trim.
	 * @param- {Object} [guard] Enables use as an iteratee for methods like `_.map`.
	 * @returns {string} Returns the trimmed string.
	 * @example
	 *
	 * _.trimEnd('  abc  ');
	 * // => '  abc'
	 *
	 * _.trimEnd('-_-abc-_-', '_-');
	 * // => '-_-abc'
	 */
	function trimEnd(string, chars, guard) {
	  string = toString(string);
	  if (string && (guard || chars === undefined)) {
	    return string.replace(reTrimEnd, '');
	  }
	  if (!string || !(chars = baseToString(chars))) {
	    return string;
	  }
	  var strSymbols = stringToArray(string),
	      end = charsEndIndex(strSymbols, stringToArray(chars)) + 1;

	  return castSlice(strSymbols, 0, end).join('');
	}

	module.exports = trimEnd;


/***/ })
/******/ ])
});
;