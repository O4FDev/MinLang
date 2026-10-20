package org.minyar.hello;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

/** Independent wire producer and malformed-input controls, no Android stubs. */
public final class MobileAndroidSnapshotTest {
    private static int checks;
    private static void expect(boolean value) {
        checks++;
        if (!value) throw new AssertionError("snapshot check " + checks);
    }
    private static void text(DataOutputStream output, String value) throws Exception {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        output.writeInt(bytes.length); output.write(bytes);
    }
    private static byte[] wire(String input, boolean checked, String key) throws Exception {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        DataOutputStream output = new DataOutputStream(buffer);
        output.writeInt(0x4d594131); output.writeLong(3); output.writeLong(2); output.writeInt(3);
        text(output, "Garden 🌕");
        output.writeInt(0); output.writeInt(7); output.writeInt(20); output.writeInt(24); output.writeInt(0);
        text(output, ""); text(output, "");
        output.writeInt(1); output.writeInt(4); output.writeInt(12); output.writeInt(0); output.writeInt(0);
        text(output, key); text(output, input);
        output.writeInt(1); output.writeInt(5); output.writeInt(12); output.writeInt(0); output.writeInt(checked ? 1 : 0);
        text(output, "welcome"); text(output, "Say hello ✓");
        return buffer.toByteArray();
    }
    private static void rejects(byte[] bytes) {
        checks++;
        try { MinyarSnapshot.decode(bytes); }
        catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("accepted invalid snapshot " + checks);
    }
    private static byte[] integer(byte[] source, int at, int value) {
        byte[] result = source.clone(); ByteBuffer.wrap(result).putInt(at, value); return result;
    }
    private static void rejectsText(String text, int maximum) {
        checks++;
        try { MinyarSnapshot.utf8(text, maximum); }
        catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("accepted invalid event text " + checks);
    }
    public static void main(String[] args) throws Exception {
        byte[] bytes = wire("Zoë 🌍", true, "name");
        MinyarSnapshot snapshot = MinyarSnapshot.decode(bytes);
        expect(snapshot.revision == 3 && snapshot.appliedEvent == 2);
        expect(snapshot.title.equals("Garden 🌕") && snapshot.nodes.length == 3);
        expect(snapshot.nodes[1].text.equals("Zoë 🌍") && snapshot.nodes[1].depth == 2);
        expect(snapshot.nodes[2].checked && snapshot.nodes[2].key.equals("welcome"));
        expect(snapshot.sameStructure(MinyarSnapshot.decode(wire("Another", false, "name"))));
        expect(!snapshot.sameStructure(MinyarSnapshot.decode(wire("Another", false, "other"))));
        expect(!snapshot.sameStructure(null));
        expect(!MinyarSnapshot.mayReplace(3, 2, false));
        expect(MinyarSnapshot.mayReplace(3, 3, false));
        expect(!MinyarSnapshot.mayReplace(0, 3, true));
        expect(new String(MinyarSnapshot.utf8("Zoë 🌕", 16), StandardCharsets.UTF_8).equals("Zoë 🌕"));
        rejectsText("\ud800", 16);
        rejectsText("\udc00", 16);
        rejectsText("zero\u0000byte", 16);
        rejectsText("🌕", 3);
        expect(MinyarSnapshot.utf8("🌕", 4).length == 4);
        rejectsText("too long", 3);
        for (int length = 0; length < bytes.length; length++) rejects(Arrays.copyOf(bytes, length));
        rejects(Arrays.copyOf(bytes, bytes.length + 1));
        rejects(integer(bytes, 0, 0));
        rejects(integer(bytes, 20, 0));
        rejects(integer(bytes, 20, 1025));
        rejects(integer(bytes, 24, Integer.MAX_VALUE));
        // Independent producer places the root immediately after title bytes.
        int root = 28 + "Garden 🌕".getBytes(StandardCharsets.UTF_8).length;
        rejects(integer(bytes, root, 1));
        rejects(integer(bytes, root + 4, 0));
        rejects(integer(bytes, root + 8, 257));
        rejects(integer(bytes, root + 12, -1));
        rejects(integer(bytes, root + 16, 2));
        int input = root + 28;
        rejects(integer(bytes, input, 0));
        rejects(integer(bytes, input, 3));
        rejects(integer(bytes, root + 4, 1));
        rejects(wire("zero\u0000byte", false, "name"));
        rejects(wire("text", false, ""));
        rejects(wire("text", false, "welcome"));
        char[] longKey = new char[257]; Arrays.fill(longKey, 'x');
        rejects(wire("text", false, new String(longKey)));
        byte[] malformed = bytes.clone();
        malformed[28] = (byte)0xff;
        rejects(malformed);
        rejects(new byte[MinyarSnapshot.MAX_BYTES + 1]);
        System.out.println(checks + " Android snapshot, UTF-8, structure and event-watermark checks passed");
    }
}
