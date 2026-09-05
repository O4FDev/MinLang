#define STB_DS_IMPLEMENTATION
#include "stb_ds.h"

#include <limits.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    TOKEN_EOF = 256,
    TOKEN_NEWLINE,
    TOKEN_NAME,
    TOKEN_TEXT,
    TOKEN_CHARACTER,
    TOKEN_INTEGER,
    TOKEN_EQUAL_EQUAL,
    TOKEN_NOT_EQUAL,
    TOKEN_LESS_EQUAL,
    TOKEN_GREATER_EQUAL,
    TOKEN_AND,
    TOKEN_OR
};

enum {
    TYPE_UNKNOWN,
    TYPE_INTEGER,
    TYPE_TEXT,
    TYPE_CHARACTER,
    TYPE_BOOLEAN,
    TYPE_NOTHING,
    TYPE_LIST_INTEGER = 101,
    TYPE_LIST_TEXT,
    TYPE_LIST_CHARACTER,
    TYPE_LIST_BOOLEAN
};

typedef int Type;

typedef struct Expression Expression;
typedef struct Statement Statement;
typedef struct Function Function;

typedef enum {
    EXPRESSION_INTEGER,
    EXPRESSION_TEXT,
    EXPRESSION_CHARACTER,
    EXPRESSION_BOOLEAN,
    EXPRESSION_NAME,
    EXPRESSION_CALL,
    EXPRESSION_UNARY,
    EXPRESSION_BINARY,
    EXPRESSION_MEMBER,
    EXPRESSION_INDEX,
    EXPRESSION_LIST,
    EXPRESSION_METHOD_CALL
} ExpressionKind;

typedef enum {
    STATEMENT_LET,
    STATEMENT_ASSIGN,
    STATEMENT_INDEX_ASSIGN,
    STATEMENT_EXPRESSION,
    STATEMENT_RETURN,
    STATEMENT_IF,
    STATEMENT_WHILE
} StatementKind;

typedef struct {
    char *name;
    Type type;
    int line;
    int column;
} Parameter;

typedef struct {
    char *name;
    Type type;
    int active;
} Local;

struct Expression {
    ExpressionKind kind;
    Type type;
    int line;
    int column;
    long long integer;
    char *text;
    size_t text_length;
    int operator;
    int local_index;
    int string_index;
    Function *function;
    Expression *left;
    Expression *right;
    Expression **arguments;
};

struct Statement {
    StatementKind kind;
    int line;
    int column;
    char *name;
    Type declared_type;
    int local_index;
    Expression *expression;
    Expression *target;
    Statement *then_body;
    Statement *else_body;
    Statement *body;
};

struct Function {
    char *name;
    Parameter *parameters;
    Type return_type;
    int return_was_written;
    Statement *body;
    Local *locals;
    int line;
    int column;
};

typedef struct {
    Function *functions;
    Expression **text_literals;
} Program;

typedef struct {
    int kind;
    char *text;
    size_t text_length;
    long long integer;
    int line;
    int column;
} Token;

typedef struct {
    const char *cursor;
    int line;
    int column;
} Lexer;

typedef struct {
    Lexer lexer;
    Token token;
    Program program;
} Parser;

typedef struct {
    FILE *output;
    Function *function;
    int next_temporary;
    int next_label;
    char current_block[64];
} Emitter;

typedef struct {
    Type type;
    char name[64];
} Value;

static const char *source_path;

static void fail_at(int line, int column, const char *format, ...) {
    va_list arguments;
    fprintf(stderr, "%s:%d:%d: error: ", source_path, line, column);
    va_start(arguments, format);
    vfprintf(stderr, format, arguments);
    va_end(arguments);
    fputc('\n', stderr);
    exit(1);
}

static void out_of_memory(void) {
    fprintf(stderr, "minyarc: out of memory\n");
    exit(1);
}

static void *allocate(size_t size) {
    void *memory = calloc(1, size);
    if (!memory)
        out_of_memory();
    return memory;
}

static char *copy_text(const char *start, size_t length) {
    char *text = allocate(length + 1);
    memcpy(text, start, length);
    return text;
}

static int peek(Lexer *lexer) {
    return (unsigned char)*lexer->cursor;
}

static int take(Lexer *lexer) {
    int c = peek(lexer);
    if (!c)
        return 0;
    lexer->cursor++;
    if (c == '\n') {
        lexer->line++;
        lexer->column = 1;
    } else {
        lexer->column++;
    }
    return c;
}

static void skip_horizontal_space_and_comments(Lexer *lexer) {
    for (;;) {
        while (peek(lexer) == ' ' || peek(lexer) == '\t' || peek(lexer) == '\r')
            take(lexer);

        if (lexer->cursor[0] == '/' && lexer->cursor[1] == '/') {
            while (peek(lexer) && peek(lexer) != '\n')
                take(lexer);
            continue;
        }

        if (lexer->cursor[0] == '/' && lexer->cursor[1] == '*') {
            int line = lexer->line;
            int column = lexer->column;
            take(lexer);
            take(lexer);
            while (peek(lexer) &&
                   !(lexer->cursor[0] == '*' && lexer->cursor[1] == '/'))
                take(lexer);
            if (!peek(lexer))
                fail_at(line, column, "this block comment is never closed");
            take(lexer);
            take(lexer);
            continue;
        }
        return;
    }
}

static int escaped_character(Lexer *lexer, int line, int column) {
    int c = take(lexer);
    switch (c) {
    case '0': return '\0';
    case 'n': return '\n';
    case 'r': return '\r';
    case 't': return '\t';
    case '\\': return '\\';
    case '"': return '"';
    case '\'': return '\'';
    default:
        fail_at(line, column, "I don't recognise the escape sequence \\%c", c);
        return 0;
    }
}

static Token next_token(Lexer *lexer) {
    Token token = {0};
    const char *start;
    char *text = NULL;

    skip_horizontal_space_and_comments(lexer);
    token.line = lexer->line;
    token.column = lexer->column;

    if (!peek(lexer)) {
        token.kind = TOKEN_EOF;
        return token;
    }
    if (peek(lexer) == '\n') {
        token.kind = TOKEN_NEWLINE;
        take(lexer);
        return token;
    }

    if ((peek(lexer) >= 'a' && peek(lexer) <= 'z') ||
        (peek(lexer) >= 'A' && peek(lexer) <= 'Z') || peek(lexer) == '_') {
        start = lexer->cursor;
        do {
            take(lexer);
        } while ((peek(lexer) >= 'a' && peek(lexer) <= 'z') ||
                 (peek(lexer) >= 'A' && peek(lexer) <= 'Z') ||
                 (peek(lexer) >= '0' && peek(lexer) <= '9') ||
                 peek(lexer) == '_');
        token.kind = TOKEN_NAME;
        token.text = copy_text(start, (size_t)(lexer->cursor - start));
        return token;
    }

    if (peek(lexer) >= '0' && peek(lexer) <= '9') {
        token.kind = TOKEN_INTEGER;
        while (peek(lexer) >= '0' && peek(lexer) <= '9') {
            int digit = peek(lexer) - '0';
            if (token.integer > (LLONG_MAX - digit) / 10)
                fail_at(token.line, token.column,
                        "this Integer is larger than Minyar currently supports");
            token.integer = token.integer * 10 + take(lexer) - '0';
        }
        return token;
    }

    if (peek(lexer) == '"') {
        take(lexer);
        while (peek(lexer) && peek(lexer) != '"') {
            int c;
            if (peek(lexer) == '\n')
                fail_at(token.line, token.column,
                        "text literals cannot continue onto the next line yet");
            c = take(lexer);
            if (c == '\\')
                c = escaped_character(lexer, token.line, token.column);
            arrput(text, (char)c);
        }
        if (!peek(lexer))
            fail_at(token.line, token.column, "this text literal is never closed");
        take(lexer);
        token.kind = TOKEN_TEXT;
        token.text_length = (size_t)arrlen(text);
        token.text = copy_text(text, token.text_length);
        arrfree(text);
        return token;
    }

    if (peek(lexer) == '\'') {
        int character;
        take(lexer);
        if (!peek(lexer) || peek(lexer) == '\n' || peek(lexer) == '\'')
            fail_at(token.line, token.column,
                    "a character literal contains exactly one character");
        character = take(lexer);
        if (character == '\\')
            character = escaped_character(lexer, token.line, token.column);
        if (peek(lexer) != '\'')
            fail_at(token.line, token.column,
                    "a character literal contains exactly one character");
        take(lexer);
        token.kind = TOKEN_CHARACTER;
        token.integer = character;
        return token;
    }

    if (lexer->cursor[0] == '=' && lexer->cursor[1] == '=') {
        take(lexer); take(lexer); token.kind = TOKEN_EQUAL_EQUAL; return token;
    }
    if (lexer->cursor[0] == '!' && lexer->cursor[1] == '=') {
        take(lexer); take(lexer); token.kind = TOKEN_NOT_EQUAL; return token;
    }
    if (lexer->cursor[0] == '<' && lexer->cursor[1] == '=') {
        take(lexer); take(lexer); token.kind = TOKEN_LESS_EQUAL; return token;
    }
    if (lexer->cursor[0] == '>' && lexer->cursor[1] == '=') {
        take(lexer); take(lexer); token.kind = TOKEN_GREATER_EQUAL; return token;
    }
    if (lexer->cursor[0] == '&' && lexer->cursor[1] == '&') {
        take(lexer); take(lexer); token.kind = TOKEN_AND; return token;
    }
    if (lexer->cursor[0] == '|' && lexer->cursor[1] == '|') {
        take(lexer); take(lexer); token.kind = TOKEN_OR; return token;
    }

    if (strchr("(){}[]:,.;+-*/%=!<>", peek(lexer))) {
        token.kind = take(lexer);
        return token;
    }

    fail_at(token.line, token.column,
            "I don't recognise the character '%c'", peek(lexer));
    return token;
}

static void discard_token(Token *token) {
    free(token->text);
    token->text = NULL;
}

static void advance(Parser *parser) {
    discard_token(&parser->token);
    parser->token = next_token(&parser->lexer);
}

static int word_is(Parser *parser, const char *word) {
    return parser->token.kind == TOKEN_NAME &&
           strcmp(parser->token.text, word) == 0;
}

static void skip_separators(Parser *parser) {
    while (parser->token.kind == TOKEN_NEWLINE || parser->token.kind == ';')
        advance(parser);
}

static void expect(Parser *parser, int kind, const char *description) {
    if (parser->token.kind != kind)
        fail_at(parser->token.line, parser->token.column,
                "I expected %s here", description);
    advance(parser);
}

static void expect_word(Parser *parser, const char *word) {
    if (!word_is(parser, word))
        fail_at(parser->token.line, parser->token.column,
                "I expected '%s' here", word);
    advance(parser);
}

static char *take_name(Parser *parser, const char *description) {
    char *name;
    if (parser->token.kind != TOKEN_NAME)
        fail_at(parser->token.line, parser->token.column,
                "I expected %s here", description);
    name = parser->token.text;
    parser->token.text = NULL;
    advance(parser);
    return name;
}

static Type parse_type(Parser *parser) {
    Type type = TYPE_UNKNOWN;
    if (word_is(parser, "Integer"))
        type = TYPE_INTEGER;
    else if (word_is(parser, "Text"))
        type = TYPE_TEXT;
    else if (word_is(parser, "Character"))
        type = TYPE_CHARACTER;
    else if (word_is(parser, "Boolean"))
        type = TYPE_BOOLEAN;
    else if (word_is(parser, "Nothing"))
        type = TYPE_NOTHING;
    else if (word_is(parser, "List")) {
        advance(parser);
        expect(parser, '<', "'<' followed by the list's element type");
        type = parse_type(parser);
        if (type < TYPE_INTEGER || type > TYPE_BOOLEAN || type == TYPE_NOTHING)
            fail_at(parser->token.line, parser->token.column,
                    "lists currently contain Integer, Text, Character, or Boolean values");
        expect(parser, '>', "a closing '>' after the list's element type");
        return TYPE_LIST_INTEGER + type - TYPE_INTEGER;
    }
    else
        fail_at(parser->token.line, parser->token.column,
                "I expected a type such as Integer, Text, Character, or Boolean");
    advance(parser);
    return type;
}

static Expression *new_expression(Parser *parser, ExpressionKind kind) {
    Expression *expression = allocate(sizeof(*expression));
    expression->kind = kind;
    expression->line = parser->token.line;
    expression->column = parser->token.column;
    expression->local_index = -1;
    expression->string_index = -1;
    return expression;
}

static Statement new_statement(Parser *parser, StatementKind kind) {
    Statement statement = {0};
    statement.kind = kind;
    statement.line = parser->token.line;
    statement.column = parser->token.column;
    statement.local_index = -1;
    return statement;
}

static Expression *parse_expression(Parser *parser);

static Expression *parse_atom(Parser *parser) {
    Expression *expression;

    if (parser->token.kind == TOKEN_INTEGER) {
        expression = new_expression(parser, EXPRESSION_INTEGER);
        expression->integer = parser->token.integer;
        advance(parser);
        return expression;
    }
    if (parser->token.kind == TOKEN_TEXT) {
        expression = new_expression(parser, EXPRESSION_TEXT);
        expression->text = parser->token.text;
        expression->text_length = parser->token.text_length;
        parser->token.text = NULL;
        expression->string_index = (int)arrlen(parser->program.text_literals);
        arrput(parser->program.text_literals, expression);
        advance(parser);
        return expression;
    }
    if (parser->token.kind == TOKEN_CHARACTER) {
        expression = new_expression(parser, EXPRESSION_CHARACTER);
        expression->integer = parser->token.integer;
        advance(parser);
        return expression;
    }
    if (word_is(parser, "true") || word_is(parser, "false")) {
        expression = new_expression(parser, EXPRESSION_BOOLEAN);
        expression->integer = word_is(parser, "true");
        advance(parser);
        return expression;
    }
    if (parser->token.kind == TOKEN_NAME) {
        expression = new_expression(parser, EXPRESSION_NAME);
        expression->text = take_name(parser, "a name");
        if (parser->token.kind == '(') {
            Expression *call = allocate(sizeof(*call));
            *call = *expression;
            free(expression);
            expression = call;
            expression->kind = EXPRESSION_CALL;
            advance(parser);
            if (parser->token.kind != ')') {
                do {
                    arrput(expression->arguments, parse_expression(parser));
                    if (parser->token.kind != ',')
                        break;
                    advance(parser);
                } while (parser->token.kind != ')');
            }
            expect(parser, ')', "a closing parenthesis");
        }
        return expression;
    }
    if (parser->token.kind == '(') {
        advance(parser);
        expression = parse_expression(parser);
        expect(parser, ')', "a closing parenthesis");
        return expression;
    }
    if (parser->token.kind == '[') {
        expression = new_expression(parser, EXPRESSION_LIST);
        advance(parser);
        expect(parser, ']', "a closing bracket for this empty list");
        return expression;
    }
    fail_at(parser->token.line, parser->token.column,
            "I expected a value or expression here");
    return NULL;
}

static Expression *parse_primary(Parser *parser) {
    Expression *expression = parse_atom(parser);
    for (;;) {
        if (parser->token.kind == '.') {
            Expression *member = new_expression(parser, EXPRESSION_MEMBER);
            advance(parser);
            member->text = take_name(parser, "a property name after '.'");
            member->left = expression;
            if (parser->token.kind == '(') {
                member->kind = EXPRESSION_METHOD_CALL;
                advance(parser);
                if (parser->token.kind != ')') {
                    do {
                        arrput(member->arguments, parse_expression(parser));
                        if (parser->token.kind != ',')
                            break;
                        advance(parser);
                    } while (parser->token.kind != ')');
                }
                expect(parser, ')', "a closing parenthesis");
            }
            expression = member;
            continue;
        }
        if (parser->token.kind == '[') {
            Expression *index = new_expression(parser, EXPRESSION_INDEX);
            advance(parser);
            index->left = expression;
            index->right = parse_expression(parser);
            expect(parser, ']', "a closing bracket");
            expression = index;
            continue;
        }
        return expression;
    }
}

static Expression *parse_unary(Parser *parser) {
    if (parser->token.kind == '!' || parser->token.kind == '-') {
        Expression *expression = new_expression(parser, EXPRESSION_UNARY);
        expression->operator = parser->token.kind;
        advance(parser);
        expression->right = parse_unary(parser);
        return expression;
    }
    return parse_primary(parser);
}

static Expression *parse_binary(Parser *parser,
                                Expression *(*next)(Parser *),
                                const int *operators, size_t count) {
    Expression *left = next(parser);
    size_t index;
    for (;;) {
        int matches = 0;
        for (index = 0; index < count; index++)
            if (parser->token.kind == operators[index])
                matches = 1;
        if (!matches)
            return left;
        {
            Expression *expression = new_expression(parser, EXPRESSION_BINARY);
            expression->operator = parser->token.kind;
            expression->left = left;
            advance(parser);
            expression->right = next(parser);
            left = expression;
        }
    }
}

static Expression *parse_product(Parser *parser) {
    static const int operators[] = {'*', '/', '%'};
    return parse_binary(parser, parse_unary, operators, 3);
}

static Expression *parse_sum(Parser *parser) {
    static const int operators[] = {'+', '-'};
    return parse_binary(parser, parse_product, operators, 2);
}

static Expression *parse_comparison(Parser *parser) {
    static const int operators[] = {'<', '>', TOKEN_LESS_EQUAL,
                                    TOKEN_GREATER_EQUAL};
    return parse_binary(parser, parse_sum, operators, 4);
}

static Expression *parse_equality(Parser *parser) {
    static const int operators[] = {TOKEN_EQUAL_EQUAL, TOKEN_NOT_EQUAL};
    return parse_binary(parser, parse_comparison, operators, 2);
}

static Expression *parse_and(Parser *parser) {
    static const int operators[] = {TOKEN_AND};
    return parse_binary(parser, parse_equality, operators, 1);
}

static Expression *parse_expression(Parser *parser) {
    static const int operators[] = {TOKEN_OR};
    return parse_binary(parser, parse_and, operators, 1);
}

static void finish_simple_statement(Parser *parser) {
    if (parser->token.kind == ';')
        advance(parser);
    if (parser->token.kind == TOKEN_NEWLINE) {
        skip_separators(parser);
        return;
    }
    if (parser->token.kind != '}')
        fail_at(parser->token.line, parser->token.column,
                "start the next statement on a new line");
}

static Statement *parse_block(Parser *parser);

static Statement parse_statement(Parser *parser) {
    Statement statement;

    if (word_is(parser, "let")) {
        statement = new_statement(parser, STATEMENT_LET);
        advance(parser);
        statement.name = take_name(parser, "a name for this value");
        if (parser->token.kind == ':') {
            advance(parser);
            statement.declared_type = parse_type(parser);
        }
        expect(parser, '=', "'=' followed by the value to store");
        statement.expression = parse_expression(parser);
        finish_simple_statement(parser);
        return statement;
    }

    if (word_is(parser, "return")) {
        statement = new_statement(parser, STATEMENT_RETURN);
        advance(parser);
        if (parser->token.kind != TOKEN_NEWLINE && parser->token.kind != ';' &&
            parser->token.kind != '}')
            statement.expression = parse_expression(parser);
        finish_simple_statement(parser);
        return statement;
    }

    if (word_is(parser, "if")) {
        statement = new_statement(parser, STATEMENT_IF);
        advance(parser);
        statement.expression = parse_expression(parser);
        statement.then_body = parse_block(parser);
        skip_separators(parser);
        if (word_is(parser, "else")) {
            advance(parser);
            statement.else_body = parse_block(parser);
        }
        return statement;
    }

    if (word_is(parser, "while")) {
        statement = new_statement(parser, STATEMENT_WHILE);
        advance(parser);
        statement.expression = parse_expression(parser);
        statement.body = parse_block(parser);
        return statement;
    }

    statement = new_statement(parser, STATEMENT_EXPRESSION);
    statement.expression = parse_expression(parser);
    if ((statement.expression->kind == EXPRESSION_NAME ||
         statement.expression->kind == EXPRESSION_INDEX) &&
        parser->token.kind == '=') {
        if (statement.expression->kind == EXPRESSION_NAME) {
            statement.kind = STATEMENT_ASSIGN;
            statement.name = statement.expression->text;
            free(statement.expression);
        } else {
            statement.kind = STATEMENT_INDEX_ASSIGN;
            statement.target = statement.expression;
        }
        advance(parser);
        statement.expression = parse_expression(parser);
    }
    finish_simple_statement(parser);
    return statement;
}

static Statement *parse_block(Parser *parser) {
    Statement *statements = NULL;
    expect(parser, '{', "an opening brace");
    skip_separators(parser);
    while (parser->token.kind != '}') {
        if (parser->token.kind == TOKEN_EOF)
            fail_at(parser->token.line, parser->token.column,
                    "this block needs a closing brace");
        arrput(statements, parse_statement(parser));
        skip_separators(parser);
    }
    advance(parser);
    return statements;
}

static Function parse_function(Parser *parser) {
    Function function = {0};
    function.line = parser->token.line;
    function.column = parser->token.column;
    expect_word(parser, "function");
    function.name = take_name(parser, "a function name");
    expect(parser, '(', "an opening parenthesis");
    if (parser->token.kind != ')') {
        do {
            Parameter parameter = {0};
            parameter.line = parser->token.line;
            parameter.column = parser->token.column;
            parameter.name = take_name(parser, "a parameter name");
            expect(parser, ':', "':' and the parameter's type");
            parameter.type = parse_type(parser);
            arrput(function.parameters, parameter);
            if (parser->token.kind != ',')
                break;
            advance(parser);
        } while (parser->token.kind != ')');
    }
    expect(parser, ')', "a closing parenthesis");
    if (parser->token.kind == ':') {
        advance(parser);
        function.return_type = parse_type(parser);
        function.return_was_written = 1;
    } else if (strcmp(function.name, "main") == 0) {
        function.return_type = TYPE_INTEGER;
    } else {
        function.return_type = TYPE_NOTHING;
    }
    function.body = parse_block(parser);
    return function;
}

static Program parse_program(char *source) {
    Parser parser = {0};
    parser.lexer.cursor = source;
    parser.lexer.line = 1;
    parser.lexer.column = 1;
    parser.token = next_token(&parser.lexer);
    skip_separators(&parser);
    while (parser.token.kind != TOKEN_EOF) {
        if (!word_is(&parser, "function"))
            fail_at(parser.token.line, parser.token.column,
                    "a Minyar file contains function declarations here");
        arrput(parser.program.functions, parse_function(&parser));
        skip_separators(&parser);
    }
    discard_token(&parser.token);
    return parser.program;
}

static const char *type_name(Type type) {
    switch (type) {
    case TYPE_INTEGER: return "Integer";
    case TYPE_TEXT: return "Text";
    case TYPE_CHARACTER: return "Character";
    case TYPE_BOOLEAN: return "Boolean";
    case TYPE_NOTHING: return "Nothing";
    case TYPE_LIST_INTEGER: return "List<Integer>";
    case TYPE_LIST_TEXT: return "List<Text>";
    case TYPE_LIST_CHARACTER: return "List<Character>";
    case TYPE_LIST_BOOLEAN: return "List<Boolean>";
    default: return "an unknown type";
    }
}

static const char *llvm_type(Type type) {
    switch (type) {
    case TYPE_INTEGER: return "i64";
    case TYPE_TEXT: return "ptr";
    case TYPE_CHARACTER: return "i32";
    case TYPE_BOOLEAN: return "i1";
    case TYPE_NOTHING: return "void";
    case TYPE_LIST_INTEGER:
    case TYPE_LIST_TEXT:
    case TYPE_LIST_CHARACTER:
    case TYPE_LIST_BOOLEAN: return "ptr";
    default: return "void";
    }
}

static Function *find_function(Program *program, const char *name) {
    size_t index;
    for (index = 0; index < (size_t)arrlen(program->functions); index++)
        if (strcmp(program->functions[index].name, name) == 0)
            return &program->functions[index];
    return NULL;
}

static int find_local(Function *function, const char *name) {
    int index;
    for (index = (int)arrlen(function->locals) - 1; index >= 0; index--)
        if (function->locals[index].active &&
            strcmp(function->locals[index].name, name) == 0)
            return index;
    return -1;
}

static int add_local(Function *function, const char *name, Type type,
                     int line, int column) {
    Local local;
    if (find_local(function, name) >= 0)
        fail_at(line, column, "'%s' already has a meaning in this function", name);
    local.name = (char *)name;
    local.type = type;
    local.active = 1;
    arrput(function->locals, local);
    return (int)arrlen(function->locals) - 1;
}

static void require_type(Expression *expression, Type actual, Type expected,
                         const char *context) {
    if (actual != expected)
        fail_at(expression->line, expression->column,
                "%s needs %s, but this expression produces %s",
                context, type_name(expected), type_name(actual));
}

static Type check_expression(Program *program, Function *function,
                             Expression *expression) {
    Type left;
    Type right;
    size_t index;

    switch (expression->kind) {
    case EXPRESSION_INTEGER:
        return expression->type = TYPE_INTEGER;
    case EXPRESSION_TEXT:
        return expression->type = TYPE_TEXT;
    case EXPRESSION_CHARACTER:
        return expression->type = TYPE_CHARACTER;
    case EXPRESSION_BOOLEAN:
        return expression->type = TYPE_BOOLEAN;
    case EXPRESSION_NAME:
        expression->local_index = find_local(function, expression->text);
        if (expression->local_index < 0)
            fail_at(expression->line, expression->column,
                    "I can't find a value named '%s'", expression->text);
        return expression->type = function->locals[expression->local_index].type;
    case EXPRESSION_CALL:
        if (strcmp(expression->text, "print") == 0) {
            if (arrlen(expression->arguments) != 1)
                fail_at(expression->line, expression->column,
                        "print expects exactly one value");
            left = check_expression(program, function, expression->arguments[0]);
            if (left == TYPE_NOTHING)
                fail_at(expression->line, expression->column,
                        "print needs a value to display");
            return expression->type = TYPE_NOTHING;
        }
        if (strcmp(expression->text, "fail") == 0) {
            if (arrlen(expression->arguments) != 1)
                fail_at(expression->line, expression->column,
                        "fail expects exactly one Text explanation");
            left = check_expression(program, function, expression->arguments[0]);
            require_type(expression->arguments[0], left, TYPE_TEXT,
                         "a failure explanation");
            return expression->type = TYPE_NOTHING;
        }
        if (strcmp(expression->text, "Text") == 0) {
            if (arrlen(expression->arguments) != 1)
                fail_at(expression->line, expression->column,
                        "Text expects exactly one value to describe");
            left = check_expression(program, function, expression->arguments[0]);
            if (left == TYPE_NOTHING)
                fail_at(expression->line, expression->column,
                        "Nothing cannot be converted to Text");
            return expression->type = TYPE_TEXT;
        }
        if (strcmp(expression->text, "joinText") == 0) {
            if (arrlen(expression->arguments) != 1)
                fail_at(expression->line, expression->column,
                        "joinText expects one List<Text>");
            left = check_expression(program, function, expression->arguments[0]);
            require_type(expression->arguments[0], left, TYPE_LIST_TEXT,
                         "the Text pieces to join");
            return expression->type = TYPE_TEXT;
        }
        if (strcmp(expression->text, "readTextFile") == 0) {
            if (arrlen(expression->arguments) != 1)
                fail_at(expression->line, expression->column,
                        "readTextFile expects one file path");
            left = check_expression(program, function, expression->arguments[0]);
            require_type(expression->arguments[0], left, TYPE_TEXT, "a file path");
            return expression->type = TYPE_TEXT;
        }
        if (strcmp(expression->text, "writeTextFile") == 0) {
            if (arrlen(expression->arguments) != 2)
                fail_at(expression->line, expression->column,
                        "writeTextFile expects a file path and some Text");
            for (index = 0; index < 2; index++) {
                left = check_expression(program, function, expression->arguments[index]);
                require_type(expression->arguments[index], left, TYPE_TEXT,
                             index == 0 ? "a file path" : "file contents");
            }
            return expression->type = TYPE_NOTHING;
        }
        if (strcmp(expression->text, "argumentCount") == 0) {
            if (arrlen(expression->arguments) != 0)
                fail_at(expression->line, expression->column,
                        "argumentCount does not take any values");
            return expression->type = TYPE_INTEGER;
        }
        if (strcmp(expression->text, "argument") == 0) {
            if (arrlen(expression->arguments) != 1)
                fail_at(expression->line, expression->column,
                        "argument expects one position");
            left = check_expression(program, function, expression->arguments[0]);
            require_type(expression->arguments[0], left, TYPE_INTEGER,
                         "an argument position");
            return expression->type = TYPE_TEXT;
        }
        expression->function = find_function(program, expression->text);
        if (!expression->function)
            fail_at(expression->line, expression->column,
                    "I can't find a function named '%s'", expression->text);
        if (arrlen(expression->arguments) != arrlen(expression->function->parameters))
            fail_at(expression->line, expression->column,
                    "%s expects %td arguments, but this call provides %td",
                    expression->text, arrlen(expression->function->parameters),
                    arrlen(expression->arguments));
        for (index = 0; index < (size_t)arrlen(expression->arguments); index++) {
            left = check_expression(program, function, expression->arguments[index]);
            require_type(expression->arguments[index], left,
                         expression->function->parameters[index].type,
                         "this function argument");
        }
        return expression->type = expression->function->return_type;
    case EXPRESSION_UNARY:
        right = check_expression(program, function, expression->right);
        if (expression->operator == '!') {
            require_type(expression->right, right, TYPE_BOOLEAN, "logical not");
            return expression->type = TYPE_BOOLEAN;
        }
        require_type(expression->right, right, TYPE_INTEGER, "negation");
        return expression->type = TYPE_INTEGER;
    case EXPRESSION_BINARY:
        left = check_expression(program, function, expression->left);
        right = check_expression(program, function, expression->right);
        if (left != right)
            fail_at(expression->line, expression->column,
                    "these two sides have different types: %s and %s",
                    type_name(left), type_name(right));
        if (expression->operator == TOKEN_EQUAL_EQUAL ||
            expression->operator == TOKEN_NOT_EQUAL) {
            if (left == TYPE_NOTHING)
                fail_at(expression->line, expression->column,
                        "Nothing cannot be compared");
            return expression->type = TYPE_BOOLEAN;
        }
        if (expression->operator == TOKEN_AND || expression->operator == TOKEN_OR) {
            require_type(expression->left, left, TYPE_BOOLEAN,
                         "a logical operation");
            return expression->type = TYPE_BOOLEAN;
        }
        if (expression->operator == '<' || expression->operator == '>' ||
            expression->operator == TOKEN_LESS_EQUAL ||
            expression->operator == TOKEN_GREATER_EQUAL) {
            if (left != TYPE_INTEGER && left != TYPE_CHARACTER)
                fail_at(expression->line, expression->column,
                        "ordered comparisons work with Integer or Character values, not %s",
                        type_name(left));
            return expression->type = TYPE_BOOLEAN;
        }
        if (expression->operator == '+' && left == TYPE_TEXT)
            return expression->type = TYPE_TEXT;
        require_type(expression->left, left, TYPE_INTEGER, "arithmetic");
        return expression->type = TYPE_INTEGER;
    case EXPRESSION_MEMBER:
        left = check_expression(program, function, expression->left);
        if (left == TYPE_TEXT && strcmp(expression->text, "byteLength") == 0)
            return expression->type = TYPE_INTEGER;
        if ((left == TYPE_TEXT ||
             (left >= TYPE_LIST_INTEGER && left <= TYPE_LIST_BOOLEAN)) &&
            strcmp(expression->text, "length") == 0)
            return expression->type = TYPE_INTEGER;
        fail_at(expression->line, expression->column,
                "%s does not have a property named '%s'",
                type_name(left), expression->text);
        return TYPE_UNKNOWN;
    case EXPRESSION_INDEX:
        left = check_expression(program, function, expression->left);
        right = check_expression(program, function, expression->right);
        require_type(expression->right, right, TYPE_INTEGER, "a position");
        if (left == TYPE_TEXT)
            return expression->type = TYPE_CHARACTER;
        if (left >= TYPE_LIST_INTEGER && left <= TYPE_LIST_BOOLEAN)
            return expression->type = TYPE_INTEGER + left - TYPE_LIST_INTEGER;
        fail_at(expression->line, expression->column,
                "%s values cannot be accessed by position", type_name(left));
        return TYPE_UNKNOWN;
    case EXPRESSION_LIST:
        if (expression->type == TYPE_UNKNOWN)
            fail_at(expression->line, expression->column,
                    "an empty list needs a type, such as 'let names: List<Text> = []'");
        return expression->type;
    case EXPRESSION_METHOD_CALL:
        left = check_expression(program, function, expression->left);
        if (left == TYPE_TEXT) {
            if (strcmp(expression->text, "slice") != 0)
                fail_at(expression->line, expression->column,
                        "Text does not provide the '%s' operation", expression->text);
            if (arrlen(expression->arguments) != 2)
                fail_at(expression->line, expression->column,
                        "Text.slice expects a starting and ending position");
            for (index = 0; index < 2; index++) {
                right = check_expression(program, function, expression->arguments[index]);
                require_type(expression->arguments[index], right, TYPE_INTEGER,
                             "a Text slice position");
            }
            return expression->type = TYPE_TEXT;
        }
        if (left < TYPE_LIST_INTEGER || left > TYPE_LIST_BOOLEAN)
            fail_at(expression->line, expression->column,
                    "%s does not provide the '%s' operation",
                    type_name(left), expression->text);
        if (strcmp(expression->text, "add") != 0)
            fail_at(expression->line, expression->column,
                    "lists do not provide an operation named '%s'", expression->text);
        if (arrlen(expression->arguments) != 1)
            fail_at(expression->line, expression->column,
                    "list.add expects exactly one value");
        right = check_expression(program, function, expression->arguments[0]);
        require_type(expression->arguments[0], right,
                     TYPE_INTEGER + left - TYPE_LIST_INTEGER,
                     "the value added to this list");
        return expression->type = TYPE_NOTHING;
    }
    return TYPE_UNKNOWN;
}

static int statement_guarantees_return(Statement *statement) {
    if (statement->kind == STATEMENT_RETURN)
        return 1;
    if (statement->kind == STATEMENT_IF && statement->else_body) {
        Statement *then_last;
        Statement *else_last;
        if (!arrlen(statement->then_body) || !arrlen(statement->else_body))
            return 0;
        then_last = &arrlast(statement->then_body);
        else_last = &arrlast(statement->else_body);
        return statement_guarantees_return(then_last) &&
               statement_guarantees_return(else_last);
    }
    return 0;
}

static void check_statements(Program *program, Function *function,
                             Statement *statements, int creates_scope) {
    size_t index;
    size_t first_scoped_local = (size_t)arrlen(function->locals);
    int returned = 0;
    for (index = 0; index < (size_t)arrlen(statements); index++) {
        Statement *statement = &statements[index];
        Type type;
        if (returned)
            fail_at(statement->line, statement->column,
                    "this statement can never run because the function already returned");
        switch (statement->kind) {
        case STATEMENT_LET:
            if (statement->expression->kind == EXPRESSION_LIST &&
                statement->declared_type >= TYPE_LIST_INTEGER &&
                statement->declared_type <= TYPE_LIST_BOOLEAN)
                statement->expression->type = statement->declared_type;
            type = check_expression(program, function, statement->expression);
            if (type == TYPE_NOTHING)
                fail_at(statement->line, statement->column,
                        "a let declaration needs a value");
            if (statement->declared_type && statement->declared_type != type)
                fail_at(statement->line, statement->column,
                        "'%s' was declared as %s but receives %s", statement->name,
                        type_name(statement->declared_type), type_name(type));
            statement->declared_type = type;
            statement->local_index = add_local(function, statement->name, type,
                                               statement->line, statement->column);
            break;
        case STATEMENT_ASSIGN:
            statement->local_index = find_local(function, statement->name);
            if (statement->local_index < 0)
                fail_at(statement->line, statement->column,
                        "I can't find a value named '%s'", statement->name);
            type = check_expression(program, function, statement->expression);
            if (type != function->locals[statement->local_index].type)
                fail_at(statement->line, statement->column,
                        "'%s' cannot change from %s to %s", statement->name,
                        type_name(function->locals[statement->local_index].type),
                        type_name(type));
            break;
        case STATEMENT_INDEX_ASSIGN: {
            Type target = check_expression(program, function, statement->target);
            if (statement->target->left->type < TYPE_LIST_INTEGER ||
                statement->target->left->type > TYPE_LIST_BOOLEAN)
                fail_at(statement->line, statement->column,
                        "only List positions can receive a new value");
            type = check_expression(program, function, statement->expression);
            if (type != target)
                fail_at(statement->line, statement->column,
                        "this List contains %s, not %s",
                        type_name(target), type_name(type));
            break;
        }
        case STATEMENT_EXPRESSION:
            check_expression(program, function, statement->expression);
            break;
        case STATEMENT_RETURN:
            type = statement->expression
                       ? check_expression(program, function, statement->expression)
                       : TYPE_NOTHING;
            if (type != function->return_type)
                fail_at(statement->line, statement->column,
                        "this function returns %s, not %s",
                        type_name(function->return_type), type_name(type));
            break;
        case STATEMENT_IF:
            type = check_expression(program, function, statement->expression);
            require_type(statement->expression, type, TYPE_BOOLEAN,
                         "an if condition");
            check_statements(program, function, statement->then_body, 1);
            check_statements(program, function, statement->else_body, 1);
            break;
        case STATEMENT_WHILE:
            type = check_expression(program, function, statement->expression);
            require_type(statement->expression, type, TYPE_BOOLEAN,
                         "a while condition");
            check_statements(program, function, statement->body, 1);
            break;
        }
        returned = statement_guarantees_return(statement);
    }
    if (creates_scope)
        for (index = first_scoped_local;
             index < (size_t)arrlen(function->locals); index++)
            function->locals[index].active = 0;
}

static void check_program(Program *program) {
    size_t function_index;
    size_t parameter_index;
    if (!find_function(program, "main"))
        fail_at(1, 1, "every program needs a function named 'main'");
    for (function_index = 0;
         function_index < (size_t)arrlen(program->functions); function_index++) {
        Function *function = &program->functions[function_index];
        size_t other;
        for (other = 0; other < function_index; other++)
            if (strcmp(program->functions[other].name, function->name) == 0)
                fail_at(function->line, function->column,
                        "there is already a function named '%s'", function->name);
        if (strcmp(function->name, "main") == 0 && arrlen(function->parameters))
            fail_at(function->line, function->column,
                    "main does not take parameters yet");
        for (parameter_index = 0;
             parameter_index < (size_t)arrlen(function->parameters);
             parameter_index++) {
            Parameter *parameter = &function->parameters[parameter_index];
            add_local(function, parameter->name, parameter->type,
                      parameter->line, parameter->column);
        }
        check_statements(program, function, function->body, 0);
        if (function->return_type != TYPE_NOTHING &&
            strcmp(function->name, "main") != 0 &&
            (!arrlen(function->body) ||
             !statement_guarantees_return(&arrlast(function->body))))
            fail_at(function->line, function->column,
                    "'%s' promises to return %s on every path",
                    function->name, type_name(function->return_type));
    }
}

static void emit_llvm_text(FILE *output, const char *text, size_t length) {
    size_t index;
    fputc('"', output);
    for (index = 0; index < length; index++) {
        unsigned char c = (unsigned char)text[index];
        if (c >= 32 && c <= 126 && c != '"' && c != '\\')
            fputc(c, output);
        else
            fprintf(output, "\\%02X", c);
    }
    fputs("\\00\"", output);
}

static Value make_value(Type type, const char *format, ...) {
    Value value = {0};
    va_list arguments;
    value.type = type;
    va_start(arguments, format);
    vsnprintf(value.name, sizeof(value.name), format, arguments);
    va_end(arguments);
    return value;
}

static int new_temporary(Emitter *emitter) {
    return emitter->next_temporary++;
}

static int new_label(Emitter *emitter) {
    return emitter->next_label++;
}

static Value emit_expression(Emitter *emitter, Expression *expression) {
    FILE *output = emitter->output;
    Value left;
    Value right;
    int temporary;
    size_t index;

    switch (expression->kind) {
    case EXPRESSION_INTEGER:
        return make_value(TYPE_INTEGER, "%lld", expression->integer);
    case EXPRESSION_TEXT:
        return make_value(TYPE_TEXT, "getelementptr (i8, ptr @.text.%d, i64 8)", expression->string_index);
    case EXPRESSION_CHARACTER:
        return make_value(TYPE_CHARACTER, "%lld", expression->integer);
    case EXPRESSION_BOOLEAN:
        return make_value(TYPE_BOOLEAN, "%s", expression->integer ? "true" : "false");
    case EXPRESSION_NAME:
        temporary = new_temporary(emitter);
        fprintf(output, "  %%value.%d = load %s, ptr %%local.%d\n", temporary,
                llvm_type(expression->type), expression->local_index);
        return make_value(expression->type, "%%value.%d", temporary);
    case EXPRESSION_CALL: {
        Value *arguments = NULL;
        for (index = 0; index < (size_t)arrlen(expression->arguments); index++)
            arrput(arguments, emit_expression(emitter, expression->arguments[index]));
        if (strcmp(expression->text, "print") == 0) {
            const char *suffix = arguments[0].type == TYPE_INTEGER ? "integer" :
                                 arguments[0].type == TYPE_CHARACTER ? "character" :
                                 arguments[0].type == TYPE_BOOLEAN ? "boolean" : "text";
            fprintf(output, "  call void @minyar_print_%s(%s %s)\n", suffix,
                    llvm_type(arguments[0].type), arguments[0].name);
            arrfree(arguments);
            return make_value(TYPE_NOTHING, "");
        }
        if (strcmp(expression->text, "fail") == 0) {
            fprintf(output, "  call void @minyar_fail(ptr %s)\n", arguments[0].name);
            arrfree(arguments);
            return make_value(TYPE_NOTHING, "");
        }
        if (strcmp(expression->text, "Text") == 0) {
            const char *suffix;
            if (arguments[0].type == TYPE_TEXT) {
                Value result = arguments[0];
                arrfree(arguments);
                return result;
            }
            suffix = arguments[0].type == TYPE_INTEGER ? "integer" :
                     arguments[0].type == TYPE_CHARACTER ? "character" : "boolean";
            temporary = new_temporary(emitter);
            fprintf(output, "  %%value.%d = call ptr @minyar_%s_text(%s %s)\n",
                    temporary, suffix, llvm_type(arguments[0].type), arguments[0].name);
            arrfree(arguments);
            return make_value(TYPE_TEXT, "%%value.%d", temporary);
        }
        if (strcmp(expression->text, "joinText") == 0) {
            temporary = new_temporary(emitter);
            fprintf(output, "  %%value.%d = call ptr @minyar_join_texts(ptr %s)\n",
                    temporary, arguments[0].name);
            arrfree(arguments);
            return make_value(TYPE_TEXT, "%%value.%d", temporary);
        }
        if (strcmp(expression->text, "readTextFile") == 0 ||
            strcmp(expression->text, "argument") == 0) {
            temporary = new_temporary(emitter);
            fprintf(output, "  %%value.%d = call ptr @minyar_%s(%s %s)\n",
                    temporary,
                    strcmp(expression->text, "argument") == 0 ? "argument" : "read_text_file",
                    llvm_type(arguments[0].type), arguments[0].name);
            arrfree(arguments);
            return make_value(TYPE_TEXT, "%%value.%d", temporary);
        }
        if (strcmp(expression->text, "argumentCount") == 0) {
            temporary = new_temporary(emitter);
            fprintf(output, "  %%value.%d = call i64 @minyar_argument_count()\n", temporary);
            arrfree(arguments);
            return make_value(TYPE_INTEGER, "%%value.%d", temporary);
        }
        if (strcmp(expression->text, "writeTextFile") == 0) {
            fprintf(output, "  call void @minyar_write_text_file(ptr %s, ptr %s)\n",
                    arguments[0].name, arguments[1].name);
            arrfree(arguments);
            return make_value(TYPE_NOTHING, "");
        }
        temporary = expression->type == TYPE_NOTHING ? -1 : new_temporary(emitter);
        if (temporary >= 0)
            fprintf(output, "  %%value.%d = ", temporary);
        else
            fputs("  ", output);
        fprintf(output, "call %s @%s(", llvm_type(expression->type), expression->text);
        for (index = 0; index < (size_t)arrlen(arguments); index++) {
            if (index)
                fputs(", ", output);
            fprintf(output, "%s %s", llvm_type(arguments[index].type),
                    arguments[index].name);
        }
        fputs(")\n", output);
        arrfree(arguments);
        return temporary < 0 ? make_value(TYPE_NOTHING, "")
                             : make_value(expression->type, "%%value.%d", temporary);
    }
    case EXPRESSION_UNARY:
        right = emit_expression(emitter, expression->right);
        temporary = new_temporary(emitter);
        if (expression->operator == '!')
            fprintf(output, "  %%value.%d = xor i1 %s, true\n", temporary, right.name);
        else {
            fprintf(output,
                    "  %%checked.%d = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %s)\n",
                    temporary, right.name);
            fprintf(output,
                    "  %%value.%d = extractvalue { i64, i1 } %%checked.%d, 0\n",
                    temporary, temporary);
            fprintf(output,
                    "  %%overflow.%d = extractvalue { i64, i1 } %%checked.%d, 1\n",
                    temporary, temporary);
            fprintf(output,
                    "  call void @minyar_check_integer_overflow(i1 %%overflow.%d)\n",
                    temporary);
        }
        return make_value(expression->type, "%%value.%d", temporary);
    case EXPRESSION_MEMBER:
        left = emit_expression(emitter, expression->left);
        temporary = new_temporary(emitter);
        if (expression->left->type == TYPE_TEXT &&
            strcmp(expression->text, "byteLength") == 0)
            fprintf(output, "  %%value.%d = call i64 @minyar_text_byte_length(ptr %s)\n",
                    temporary, left.name);
        else
            fprintf(output, "  %%value.%d = call i64 @minyar_%s_length(ptr %s)\n",
                    temporary,
                    expression->left->type == TYPE_TEXT ? "text" : "list",
                    left.name);
        return make_value(TYPE_INTEGER, "%%value.%d", temporary);
    case EXPRESSION_INDEX:
        left = emit_expression(emitter, expression->left);
        right = emit_expression(emitter, expression->right);
        temporary = new_temporary(emitter);
        if (expression->left->type == TYPE_TEXT) {
            fprintf(output,
                    "  %%value.%d = call i32 @minyar_text_character_at(ptr %s, i64 %s)\n",
                    temporary, left.name, right.name);
            return make_value(TYPE_CHARACTER, "%%value.%d", temporary);
        } else {
            int raw = temporary;
            Type element = expression->type;
            fprintf(output,
                    "  %%value.%d = call i64 @minyar_list_get(ptr %s, i64 %s)\n",
                    raw, left.name, right.name);
            if (element == TYPE_INTEGER)
                return make_value(TYPE_INTEGER, "%%value.%d", raw);
            temporary = new_temporary(emitter);
            if (element == TYPE_TEXT)
                fprintf(output, "  %%value.%d = inttoptr i64 %%value.%d to ptr\n",
                        temporary, raw);
            else
                fprintf(output, "  %%value.%d = trunc i64 %%value.%d to %s\n",
                        temporary, raw, llvm_type(element));
            return make_value(element, "%%value.%d", temporary);
        }
    case EXPRESSION_LIST:
        temporary = new_temporary(emitter);
        fprintf(output, "  %%value.%d = call ptr @minyar_list_new()\n", temporary);
        return make_value(expression->type, "%%value.%d", temporary);
    case EXPRESSION_METHOD_CALL:
        left = emit_expression(emitter, expression->left);
        if (expression->left->type == TYPE_TEXT) {
            Value end;
            right = emit_expression(emitter, expression->arguments[0]);
            end = emit_expression(emitter, expression->arguments[1]);
            temporary = new_temporary(emitter);
            fprintf(output,
                    "  %%value.%d = call ptr @minyar_text_slice(ptr %s, i64 %s, i64 %s)\n",
                    temporary, left.name, right.name, end.name);
            return make_value(TYPE_TEXT, "%%value.%d", temporary);
        }
        right = emit_expression(emitter, expression->arguments[0]);
        if (right.type != TYPE_INTEGER) {
            temporary = new_temporary(emitter);
            if (right.type == TYPE_TEXT)
                fprintf(output, "  %%value.%d = ptrtoint ptr %s to i64\n",
                        temporary, right.name);
            else
                fprintf(output, "  %%value.%d = zext %s %s to i64\n", temporary,
                        llvm_type(right.type), right.name);
            right = make_value(TYPE_INTEGER, "%%value.%d", temporary);
        }
        fprintf(output, "  call void @minyar_list_add(ptr %s, i64 %s)\n",
                left.name, right.name);
        return make_value(TYPE_NOTHING, "");
    case EXPRESSION_BINARY:
        left = emit_expression(emitter, expression->left);
        if (expression->operator == TOKEN_AND || expression->operator == TOKEN_OR) {
            int right_label = new_label(emitter);
            int end_label = new_label(emitter);
            char left_block[64];
            char right_block[64];
            snprintf(left_block, sizeof(left_block), "%s", emitter->current_block);
            if (expression->operator == TOKEN_AND)
                fprintf(output,
                        "  br i1 %s, label %%logical.right.%d, label %%logical.end.%d\n",
                        left.name, right_label, end_label);
            else
                fprintf(output,
                        "  br i1 %s, label %%logical.end.%d, label %%logical.right.%d\n",
                        left.name, end_label, right_label);
            fprintf(output, "\nlogical.right.%d:\n", right_label);
            snprintf(emitter->current_block, sizeof(emitter->current_block),
                     "logical.right.%d", right_label);
            right = emit_expression(emitter, expression->right);
            snprintf(right_block, sizeof(right_block), "%s", emitter->current_block);
            fprintf(output, "  br label %%logical.end.%d\n", end_label);
            fprintf(output, "\nlogical.end.%d:\n", end_label);
            snprintf(emitter->current_block, sizeof(emitter->current_block),
                     "logical.end.%d", end_label);
            temporary = new_temporary(emitter);
            fprintf(output, "  %%value.%d = phi i1 [ %s, %%%s ], [ %s, %%%s ]\n",
                    temporary,
                    expression->operator == TOKEN_AND ? "false" : "true",
                    left_block, right.name, right_block);
            return make_value(TYPE_BOOLEAN, "%%value.%d", temporary);
        }
        right = emit_expression(emitter, expression->right);
        temporary = new_temporary(emitter);
        if (expression->operator == '+' && left.type == TYPE_TEXT) {
            fprintf(output, "  %%value.%d = call ptr @minyar_join_text(ptr %s, ptr %s)\n",
                    temporary, left.name, right.name);
            return make_value(TYPE_TEXT, "%%value.%d", temporary);
        }
        if ((expression->operator == TOKEN_EQUAL_EQUAL ||
             expression->operator == TOKEN_NOT_EQUAL) && left.type == TYPE_TEXT) {
            fprintf(output,
                    "  %%value.%d = call i1 @minyar_texts_are_equal(ptr %s, ptr %s)\n",
                    temporary, left.name, right.name);
            if (expression->operator == TOKEN_NOT_EQUAL) {
                int opposite = new_temporary(emitter);
                fprintf(output, "  %%value.%d = xor i1 %%value.%d, true\n",
                        opposite, temporary);
                temporary = opposite;
            }
            return make_value(TYPE_BOOLEAN, "%%value.%d", temporary);
        }
        switch (expression->operator) {
        case '+':
        case '-':
        case '*': {
            const char *operation = expression->operator == '+' ? "sadd" :
                                    expression->operator == '-' ? "ssub" : "smul";
            fprintf(output,
                    "  %%checked.%d = call { i64, i1 } @llvm.%s.with.overflow.i64(i64 %s, i64 %s)\n",
                    temporary, operation, left.name, right.name);
            fprintf(output,
                    "  %%value.%d = extractvalue { i64, i1 } %%checked.%d, 0\n",
                    temporary, temporary);
            fprintf(output,
                    "  %%overflow.%d = extractvalue { i64, i1 } %%checked.%d, 1\n",
                    temporary, temporary);
            fprintf(output,
                    "  call void @minyar_check_integer_overflow(i1 %%overflow.%d)\n",
                    temporary);
            break;
        }
        case '/':
        case '%':
            fprintf(output,
                    "  call void @minyar_check_integer_division(i64 %s, i64 %s)\n",
                    left.name, right.name);
            fprintf(output, "  %%value.%d = %s i64 %s, %s\n", temporary,
                    expression->operator == '/' ? "sdiv" : "srem",
                    left.name, right.name);
            break;
        case '<': fprintf(output, "  %%value.%d = icmp slt %s %s, %s\n", temporary, llvm_type(left.type), left.name, right.name); break;
        case '>': fprintf(output, "  %%value.%d = icmp sgt %s %s, %s\n", temporary, llvm_type(left.type), left.name, right.name); break;
        case TOKEN_LESS_EQUAL: fprintf(output, "  %%value.%d = icmp sle %s %s, %s\n", temporary, llvm_type(left.type), left.name, right.name); break;
        case TOKEN_GREATER_EQUAL: fprintf(output, "  %%value.%d = icmp sge %s %s, %s\n", temporary, llvm_type(left.type), left.name, right.name); break;
        case TOKEN_EQUAL_EQUAL:
            fprintf(output, "  %%value.%d = icmp eq %s %s, %s\n", temporary,
                    llvm_type(left.type), left.name, right.name); break;
        case TOKEN_NOT_EQUAL:
            fprintf(output, "  %%value.%d = icmp ne %s %s, %s\n", temporary,
                    llvm_type(left.type), left.name, right.name); break;
        }
        return make_value(expression->type, "%%value.%d", temporary);
    }
    return make_value(TYPE_NOTHING, "");
}

static int emit_statements(Emitter *emitter, Statement *statements);

static int emit_statement(Emitter *emitter, Statement *statement) {
    FILE *output = emitter->output;
    Value value;
    int then_label;
    int else_label;
    int end_label;
    int then_returns;
    int else_returns;

    switch (statement->kind) {
    case STATEMENT_LET:
    case STATEMENT_ASSIGN:
        value = emit_expression(emitter, statement->expression);
        fprintf(output, "  store %s %s, ptr %%local.%d\n", llvm_type(value.type),
                value.name, statement->local_index);
        return 0;
    case STATEMENT_INDEX_ASSIGN: {
        Value list = emit_expression(emitter, statement->target->left);
        Value position = emit_expression(emitter, statement->target->right);
        value = emit_expression(emitter, statement->expression);
        if (value.type != TYPE_INTEGER) {
            int converted = new_temporary(emitter);
            if (value.type == TYPE_TEXT)
                fprintf(output, "  %%value.%d = ptrtoint ptr %s to i64\n",
                        converted, value.name);
            else
                fprintf(output, "  %%value.%d = zext %s %s to i64\n", converted,
                        llvm_type(value.type), value.name);
            value = make_value(TYPE_INTEGER, "%%value.%d", converted);
        }
        fprintf(output, "  call void @minyar_list_set(ptr %s, i64 %s, i64 %s)\n",
                list.name, position.name, value.name);
        return 0;
    }
    case STATEMENT_EXPRESSION:
        emit_expression(emitter, statement->expression);
        return 0;
    case STATEMENT_RETURN:
        if (!statement->expression) {
            fputs("  ret void\n", output);
        } else {
            value = emit_expression(emitter, statement->expression);
            if (strcmp(emitter->function->name, "main") == 0) {
                int temporary = new_temporary(emitter);
                fprintf(output, "  %%value.%d = trunc i64 %s to i32\n", temporary,
                        value.name);
                fprintf(output, "  ret i32 %%value.%d\n", temporary);
            } else {
                fprintf(output, "  ret %s %s\n", llvm_type(value.type), value.name);
            }
        }
        return 1;
    case STATEMENT_IF:
        value = emit_expression(emitter, statement->expression);
        then_label = new_label(emitter);
        else_label = new_label(emitter);
        end_label = new_label(emitter);
        fprintf(output, "  br i1 %s, label %%if.then.%d, label %%%s.%d\n",
                value.name, then_label,
                statement->else_body ? "if.else" : "if.end",
                statement->else_body ? else_label : end_label);
        fprintf(output, "\nif.then.%d:\n", then_label);
        snprintf(emitter->current_block, sizeof(emitter->current_block),
                 "if.then.%d", then_label);
        then_returns = emit_statements(emitter, statement->then_body);
        if (!then_returns)
            fprintf(output, "  br label %%if.end.%d\n", end_label);
        else_returns = 0;
        if (statement->else_body) {
            fprintf(output, "\nif.else.%d:\n", else_label);
            snprintf(emitter->current_block, sizeof(emitter->current_block),
                     "if.else.%d", else_label);
            else_returns = emit_statements(emitter, statement->else_body);
            if (!else_returns)
                fprintf(output, "  br label %%if.end.%d\n", end_label);
        }
        if (!(then_returns && statement->else_body && else_returns)) {
            fprintf(output, "\nif.end.%d:\n", end_label);
            snprintf(emitter->current_block, sizeof(emitter->current_block),
                     "if.end.%d", end_label);
        }
        return then_returns && statement->else_body && else_returns;
    case STATEMENT_WHILE:
        then_label = new_label(emitter);
        else_label = new_label(emitter);
        end_label = new_label(emitter);
        fprintf(output, "  br label %%while.condition.%d\n", then_label);
        fprintf(output, "\nwhile.condition.%d:\n", then_label);
        snprintf(emitter->current_block, sizeof(emitter->current_block),
                 "while.condition.%d", then_label);
        value = emit_expression(emitter, statement->expression);
        fprintf(output, "  br i1 %s, label %%while.body.%d, label %%while.end.%d\n",
                value.name, else_label, end_label);
        fprintf(output, "\nwhile.body.%d:\n", else_label);
        snprintf(emitter->current_block, sizeof(emitter->current_block),
                 "while.body.%d", else_label);
        if (!emit_statements(emitter, statement->body))
            fprintf(output, "  br label %%while.condition.%d\n", then_label);
        fprintf(output, "\nwhile.end.%d:\n", end_label);
        snprintf(emitter->current_block, sizeof(emitter->current_block),
                 "while.end.%d", end_label);
        return 0;
    }
    return 0;
}

static int emit_statements(Emitter *emitter, Statement *statements) {
    size_t index;
    for (index = 0; index < (size_t)arrlen(statements); index++)
        if (emit_statement(emitter, &statements[index]))
            return 1;
    return 0;
}

static void emit_program(FILE *output, Program *program) {
    size_t index;
    size_t parameter_index;
    Emitter emitter = {0};
    emitter.output = output;

    fputs("; Generated by Minyar's temporary stage-zero compiler.\n\n", output);
    for (index = 0; index < (size_t)arrlen(program->text_literals); index++) {
        Expression *text = program->text_literals[index];
        fprintf(output, "@.text.data.%zu = private unnamed_addr constant [%zu x i8] c",
                index, text->text_length + 1);
        emit_llvm_text(output, text->text, text->text_length);
        fputc('\n', output);
        fprintf(output,
                "@.text.%zu = private global { i64, ptr, i64, i64, ptr } { i64 0, ptr @.text.data.%zu, i64 %zu, i64 -1, ptr null }\n",
                index, index, text->text_length);
    }
    fputs("\ndeclare void @minyar_print_integer(i64)\n"
          "declare void @minyar_print_text(ptr)\n"
          "declare void @minyar_print_character(i32)\n"
          "declare void @minyar_print_boolean(i1)\n"
          "declare void @minyar_fail(ptr)\n"
          "declare i1 @minyar_texts_are_equal(ptr, ptr)\n"
          "declare ptr @minyar_join_text(ptr, ptr)\n"
          "declare ptr @minyar_join_texts(ptr)\n"
          "declare i64 @minyar_text_length(ptr)\n"
          "declare i64 @minyar_text_byte_length(ptr)\n"
          "declare i32 @minyar_text_character_at(ptr, i64)\n"
          "declare ptr @minyar_text_slice(ptr, i64, i64)\n"
          "declare ptr @minyar_integer_text(i64)\n"
          "declare ptr @minyar_character_text(i32)\n"
          "declare ptr @minyar_boolean_text(i1)\n"
          "declare void @minyar_initialize_arguments(i32, ptr)\n"
          "declare i64 @minyar_argument_count()\n"
          "declare ptr @minyar_argument(i64)\n"
          "declare ptr @minyar_read_text_file(ptr)\n"
          "declare void @minyar_write_text_file(ptr, ptr)\n"
          "declare ptr @minyar_list_new()\n"
          "declare void @minyar_list_add(ptr, i64)\n"
          "declare i64 @minyar_list_length(ptr)\n"
          "declare i64 @minyar_list_get(ptr, i64)\n"
          "declare void @minyar_list_set(ptr, i64, i64)\n"
          "declare void @minyar_check_integer_overflow(i1)\n"
          "declare void @minyar_check_integer_division(i64, i64)\n"
          "declare { i64, i1 } @llvm.sadd.with.overflow.i64(i64, i64)\n"
          "declare { i64, i1 } @llvm.ssub.with.overflow.i64(i64, i64)\n"
          "declare { i64, i1 } @llvm.smul.with.overflow.i64(i64, i64)\n\n",
          output);

    for (index = 0; index < (size_t)arrlen(program->functions); index++) {
        Function *function = &program->functions[index];
        Type emitted_return = strcmp(function->name, "main") == 0
                                ? TYPE_UNKNOWN : function->return_type;
        emitter.function = function;
        emitter.next_temporary = 0;
        emitter.next_label = 0;
        snprintf(emitter.current_block, sizeof(emitter.current_block), "entry");
        fprintf(output, "define %s @%s(", emitted_return == TYPE_UNKNOWN
                ? "i32" : llvm_type(emitted_return), function->name);
        if (strcmp(function->name, "main") == 0) {
            fputs("i32 %minyar.argument.count, ptr %minyar.argument.values", output);
        } else for (parameter_index = 0;
                    parameter_index < (size_t)arrlen(function->parameters);
                    parameter_index++) {
            if (parameter_index)
                fputs(", ", output);
            fprintf(output, "%s %%argument.%zu",
                    llvm_type(function->parameters[parameter_index].type),
                    parameter_index);
        }
        fputs(") {\nentry:\n", output);
        if (strcmp(function->name, "main") == 0)
            fputs("  call void @minyar_initialize_arguments(i32 %minyar.argument.count, ptr %minyar.argument.values)\n",
                  output);
        for (parameter_index = 0;
             parameter_index < (size_t)arrlen(function->locals);
             parameter_index++)
            fprintf(output, "  %%local.%zu = alloca %s\n", parameter_index,
                    llvm_type(function->locals[parameter_index].type));
        for (parameter_index = 0;
             parameter_index < (size_t)arrlen(function->parameters);
             parameter_index++)
            fprintf(output, "  store %s %%argument.%zu, ptr %%local.%zu\n",
                    llvm_type(function->parameters[parameter_index].type),
                    parameter_index, parameter_index);
        if (!emit_statements(&emitter, function->body)) {
            if (strcmp(function->name, "main") == 0)
                fputs("  ret i32 0\n", output);
            else if (function->return_type == TYPE_NOTHING)
                fputs("  ret void\n", output);
            else
                fputs("  unreachable\n", output);
        }
        fputs("}\n\n", output);
    }
}

static char *read_file(const char *path) {
    FILE *file = fopen(path, "rb");
    long length;
    char *source;
    if (!file) {
        fprintf(stderr, "minyarc: I couldn't open %s\n", path);
        exit(1);
    }
    if (fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fprintf(stderr, "minyarc: I couldn't read %s\n", path);
        exit(1);
    }
    source = allocate((size_t)length + 1);
    if (fread(source, 1, (size_t)length, file) != (size_t)length) {
        fprintf(stderr, "minyarc: I couldn't read %s\n", path);
        exit(1);
    }
    fclose(file);
    return source;
}

int main(int argc, char **argv) {
    char *source;
    Program program;
    FILE *output = stdout;

    if (argc != 2 && argc != 4) {
        fprintf(stderr, "usage: minyarc FILE.min [-o FILE.ll]\n");
        return 2;
    }
    if (argc == 4 && strcmp(argv[2], "-o") != 0) {
        fprintf(stderr, "usage: minyarc FILE.min [-o FILE.ll]\n");
        return 2;
    }
    source_path = argv[1];
    source = read_file(source_path);
    program = parse_program(source);
    check_program(&program);
    if (argc == 4) {
        output = fopen(argv[3], "wb");
        if (!output) {
            fprintf(stderr, "minyarc: I couldn't write %s\n", argv[3]);
            return 1;
        }
    }
    emit_program(output, &program);
    if (output != stdout)
        fclose(output);
    free(source);
    return 0;
}
