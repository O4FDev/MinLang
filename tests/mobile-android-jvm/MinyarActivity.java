package org.minyar.hello;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicInteger;

/** Real JNI/provider/model execution in a desktop JVM; no Android UI stubs. */
public final class MinyarActivity {
    static { System.loadLibrary("minyar_ui_test"); }
    private static final Semaphore frames = new Semaphore(0);
    private static native void nativeRun();
    private static native long nativeAttach();
    private static native void nativeDetach(long token);
    private static native byte[] nativeSnapshot(long token);
    private static native long nativeEvent(long token, int node, int kind, byte[] key, byte[] text, boolean checked);
    private static native void nativeStop();
    private static final AtomicInteger checks = new AtomicInteger();
    private static void expect(boolean value) {
        int number = checks.incrementAndGet();
        if (!value) throw new AssertionError("Android JNI check " + number);
    }
    private static void requestFrame() {
        expect(Thread.currentThread().getName().equals("Minyar model"));
        frames.release();
    }
    private static MinyarSnapshot await(long token, long sequence) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(20);
        for (;;) {
            byte[] bytes = nativeSnapshot(token);
            if (bytes != null) {
                MinyarSnapshot view = MinyarSnapshot.decode(bytes);
                if (view.appliedEvent >= sequence) return view;
            }
            long remaining = deadline - System.nanoTime();
            if (remaining <= 0 || !frames.tryAcquire(remaining, TimeUnit.NANOSECONDS))
                throw new AssertionError("missing Android snapshot for event " + sequence);
        }
    }
    private static int node(MinyarSnapshot snapshot, String key) {
        for (int index = 0; index < snapshot.nodes.length; index++)
            if (snapshot.nodes[index].key.equals(key)) return index + 1;
        throw new AssertionError("missing control " + key);
    }
    private static void label(MinyarSnapshot snapshot, String value) {
        for (MinyarSnapshot.Node item : snapshot.nodes)
            if (item.kind == 1 && item.text.equals(value)) { expect(true); return; }
        throw new AssertionError("missing label " + value);
    }
    private static long post(long token, MinyarSnapshot snapshot, String key, int kind, String text, boolean checked) {
        byte[] keyBytes = key.getBytes(StandardCharsets.UTF_8), textBytes = text.getBytes(StandardCharsets.UTF_8);
        long sequence = nativeEvent(token, node(snapshot, key), kind, keyBytes, textBytes, checked);
        expect(sequence > 0);
        java.util.Arrays.fill(keyBytes, (byte)'x');
        java.util.Arrays.fill(textBytes, (byte)'x');
        return sequence;
    }
    public static void main(String[] arguments) throws Exception {
        AtomicReference<Throwable> error = new AtomicReference<>();
        long token = nativeAttach(); expect(token > 0);
        Thread worker = new Thread(() -> {
            try { nativeRun(); } catch (Throwable failure) { error.set(failure); }
        }, "Minyar model");
        worker.start();
        try {
            MinyarSnapshot initial = await(token, 0);
            expect(initial.title.equals("Minyar") && initial.nodes.length == 8);
            label(initial, "Hello, Ada!");
            label(initial, "You have sent 0 little lights.");
            long sequence = post(token, initial, "light", 1, "", false);
            MinyarSnapshot after = await(token, sequence);
            label(after, "You have sent 1 little lights.");
            sequence = post(token, after, "name", 2, "Zoë 🌕", false);
            after = await(token, sequence);
            label(after, "Hello, Zoë 🌕!");
            sequence = post(token, after, "welcome", 2, "", false);
            after = await(token, sequence);
            label(after, "A little quiet, a little light.");
            sequence = post(token, after, "welcome", 2, "", true);
            after = await(token, sequence);
            label(after, "Hello, Zoë 🌕!");
            for (int index = 0; index < 10; index++) sequence = post(token, after, "light", 1, "", false);
            after = await(token, sequence);
            label(after, "You have sent 11 little lights.");
            byte[] oldCopy = nativeSnapshot(token);
            oldCopy[0] = 0;
            expect(MinyarSnapshot.decode(nativeSnapshot(token)).revision == after.revision);
            // Admission owns the bytes even if the Activity detaches immediately.
            sequence = post(token, after, "light", 1, "", false);
            long previous = token;
            nativeDetach(previous);
            expect(nativeSnapshot(previous) == null);
            token = nativeAttach(); expect(token > previous);
            nativeDetach(previous); // A stale detach cannot clear the new host.
            after = await(token, sequence);
            label(after, "You have sent 12 little lights.");
            expect(nativeEvent(previous, node(after, "light"), 1, new byte[]{'l'}, new byte[0], false) == 0);
            expect(nativeEvent(token, node(after, "name"), 2, "name".getBytes(StandardCharsets.UTF_8), new byte[]{0}, false) == 0);
            expect(nativeEvent(token, node(after, "name"), 2, "name".getBytes(StandardCharsets.UTF_8), new byte[]{(byte)0xff}, false) == 0);
            expect(nativeEvent(token, node(after, "name"), 2, "name".getBytes(StandardCharsets.UTF_8), new byte[16385], false) == 0);
            Thread duplicate = new Thread(() -> nativeRun(), "duplicate model");
            duplicate.start(); duplicate.join(5000); expect(!duplicate.isAlive());
        } finally {
            nativeStop();
            worker.join(20000);
        }
        expect(!worker.isAlive());
        if (error.get() != null) throw new AssertionError("model worker failed", error.get());
        expect(nativeAttach() == 0);
        System.out.println(checks.get() + " real JNI model, Unicode, event-copy, rebinding and worker checks passed");
    }
}
