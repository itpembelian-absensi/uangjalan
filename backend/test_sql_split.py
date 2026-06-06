def split_sql_statements(sql: str) -> list[str]:
    statements = []
    current_statement = []
    in_string = False
    
    i = 0
    while i < len(sql):
        char = sql[i]
        
        if in_string:
            if char == '\\':
                current_statement.append(char)
                i += 1
                if i < len(sql):
                    current_statement.append(sql[i])
            elif char == "'":
                in_string = False
                current_statement.append(char)
            else:
                current_statement.append(char)
        else:
            if char == "'":
                in_string = True
                current_statement.append(char)
            elif char == ';':
                statements.append("".join(current_statement))
                current_statement = []
            else:
                current_statement.append(char)
        i += 1

    if current_statement:
        stmt = "".join(current_statement).strip()
        if stmt:
            statements.append(stmt)
            
    return statements

sql = "INSERT INTO table VALUES (1, 'foo;bar', 'baz'); UPDATE table SET a = 1;"
print(split_sql_statements(sql))
