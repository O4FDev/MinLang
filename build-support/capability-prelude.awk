# Embed compiler-owned capability declarations without runtime file reads.
BEGIN { printf "function builtinCapabilitySource(): Text { return \"" }
{
    for (position = 1; position <= length($0); position++) {
        character = substr($0, position, 1)
        if (character == "\\") printf "\\\\"
        else if (character == "\"") printf "\\\""
        else if (character == "\r") printf "\\r"
        else if (character == "\t") printf "\\t"
        else printf "%s", character
    }
    printf "\\n"
}
END { print "\" }" }
