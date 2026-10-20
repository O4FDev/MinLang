package org.minyar.hello;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;

/** Copied wire descriptions; this class has no Android or native dependency. */
final class MinyarSnapshot {
    static final int MAX_BYTES = 1024 * 1024;
    static final int MAX_TEXT = 16 * 1024;
    final long revision, appliedEvent;
    final String title;
    final Node[] nodes;

    static final class Node {
        final int parent, kind, spacing, padding, depth;
        final boolean checked;
        final String key, text;

        Node(int parent, int kind, int spacing, int padding, boolean checked,
             int depth, String key, String text) {
            this.parent = parent; this.kind = kind; this.spacing = spacing;
            this.padding = padding; this.checked = checked; this.depth = depth;
            this.key = key; this.text = text;
        }
    }

    private MinyarSnapshot(long revision, long appliedEvent, String title, Node[] nodes) {
        this.revision = revision; this.appliedEvent = appliedEvent;
        this.title = title; this.nodes = nodes;
    }

    private static String text(ByteBuffer wire, int maximum) {
        int size = wire.getInt();
        if (size < 0 || size > maximum || size > wire.remaining())
            throw new IllegalArgumentException("invalid Android snapshot text length");
        ByteBuffer bytes = wire.slice();
        bytes.limit(size);
        wire.position(wire.position() + size);
        try {
            String value = StandardCharsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(bytes).toString();
            if (value.indexOf('\u0000') >= 0)
                throw new IllegalArgumentException("zero byte in Android snapshot text");
            return value;
        } catch (CharacterCodingException error) {
            throw new IllegalArgumentException("invalid Android snapshot UTF-8", error);
        }
    }

    static MinyarSnapshot decode(byte[] bytes) {
        if (bytes.length > MAX_BYTES) throw new IllegalArgumentException("Android snapshot is too large");
        try {
            ByteBuffer wire = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN);
            if (wire.getInt() != 0x4d594131) throw new IllegalArgumentException("unknown Android snapshot format");
            long revision = wire.getLong(), applied = wire.getLong();
            int count = wire.getInt();
            if (revision <= 0 || applied < 0 || count < 1 || count > 1024)
                throw new IllegalArgumentException("invalid Android snapshot header");
            String title = text(wire, MAX_TEXT);
            Node[] nodes = new Node[count];
            HashSet<String> keys = new HashSet<>();
            for (int index = 0; index < count; index++) {
                int parent = wire.getInt(), kind = wire.getInt();
                int spacing = wire.getInt(), padding = wire.getInt(), checked = wire.getInt();
                if (parent < 0 || parent > index || (parent == 0) != (index == 0)
                    || kind < 1 || kind > 7 || spacing < 0 || spacing > 256
                    || padding < 0 || padding > 256 || checked < 0 || checked > 1)
                    throw new IllegalArgumentException("invalid Android snapshot node");
                int depth = parent == 0 ? 1 : nodes[parent - 1].depth + 1;
                if (depth > 64 || (parent != 0 && nodes[parent - 1].kind < 6))
                    throw new IllegalArgumentException("invalid Android snapshot tree");
                String key = text(wire, 256), value = text(wire, MAX_TEXT);
                if (kind >= 3 && kind <= 5 && (key.isEmpty() || !keys.add(key)))
                    throw new IllegalArgumentException("invalid Android control key");
                nodes[index] = new Node(parent, kind, spacing, padding, checked == 1, depth, key, value);
            }
            if (wire.hasRemaining()) throw new IllegalArgumentException("extra Android snapshot bytes");
            return new MinyarSnapshot(revision, applied, title, nodes);
        } catch (java.nio.BufferUnderflowException error) {
            throw new IllegalArgumentException("truncated Android snapshot", error);
        }
    }

    boolean sameStructure(MinyarSnapshot other) {
        if (other == null || nodes.length != other.nodes.length) return false;
        for (int index = 0; index < nodes.length; index++) {
            Node a = nodes[index], b = other.nodes[index];
            if (a.parent != b.parent || a.kind != b.kind || !a.key.equals(b.key)) return false;
        }
        return true;
    }

    static boolean mayReplace(long pendingEvent, long appliedEvent, boolean composing) {
        return pendingEvent <= appliedEvent && !composing;
    }

    static byte[] utf8(String value, int maximum) {
        // UTF-8 has at least as many bytes as the UTF-16 code-unit count.
        if (value.length() > maximum || value.indexOf('\u0000') >= 0)
            throw new IllegalArgumentException("Android event text exceeds its limit or contains zero");
        try {
            ByteBuffer encoded = StandardCharsets.UTF_8.newEncoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).encode(CharBuffer.wrap(value));
            if (encoded.remaining() > maximum) throw new IllegalArgumentException("Android event text exceeds its UTF-8 limit");
            byte[] bytes = new byte[encoded.remaining()];
            encoded.get(bytes);
            return bytes;
        } catch (CharacterCodingException error) {
            throw new IllegalArgumentException("Android event text contains an incomplete surrogate", error);
        }
    }
}
