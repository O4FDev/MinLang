package org.minyar.hello;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.BaseInputConnection;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.view.inputmethod.InputConnectionWrapper;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;
import java.lang.ref.WeakReference;
import java.util.HashMap;

/** One Java UI thread and one process-lifetime native model worker. */
public final class MinyarActivity extends Activity {
    static { System.loadLibrary("minyar_ui"); }
    private static final Handler UI = new Handler(Looper.getMainLooper());
    private static WeakReference<MinyarActivity> current = new WeakReference<>(null);
    private static boolean workerStarted, frameQueued;
    private static native void nativeRun();
    private static native long nativeAttach();
    private static native void nativeDetach(long token);
    private static native byte[] nativeSnapshot(long token);
    private static native long nativeEvent(long token, int node, int kind, byte[] key, byte[] text, boolean checked);

    // JNI calls this on the native model worker. Coalesce notifications without
    // a repeating UI timer; never retain an Activity from native code.
    private static void requestFrame() {
        synchronized (MinyarActivity.class) {
            if (frameQueued) return;
            frameQueued = true;
        }
        UI.post(() -> {
            synchronized (MinyarActivity.class) { frameQueued = false; }
            MinyarActivity activity = current.get();
            if (activity != null && activity.token != 0) activity.renderLatest();
        });
    }

    private long token;
    private boolean applying;
    private ScrollView scroll;
    private MinyarSnapshot snapshot;
    private View[] controls;
    private LinearLayout[] boxes;
    private final HashMap<String, Long> pending = new HashMap<>();

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        setContentView(scroll);
    }

    @Override public void onStart() {
        super.onStart();
        token = nativeAttach();
        current = new WeakReference<>(this);
        synchronized (MinyarActivity.class) {
            if (!workerStarted) {
                workerStarted = true;
                Thread worker = new Thread(() -> nativeRun(), "Minyar model");
                worker.start();
            }
        }
        requestFrame();
    }

    @Override public void onStop() {
        long oldToken = token;
        token = 0;
        nativeDetach(oldToken);
        if (current.get() == this) current = new WeakReference<>(null);
        super.onStop();
    }

    private int points(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void send(int index, int kind, String text, boolean checked) {
        if (applying || token == 0 || snapshot == null) return;
        MinyarSnapshot.Node node = snapshot.nodes[index];
        long accepted = 0;
        try {
            byte[] bytes = MinyarSnapshot.utf8(text, MinyarSnapshot.MAX_TEXT);
            accepted = nativeEvent(token, index + 1, kind, MinyarSnapshot.utf8(node.key, 256), bytes, checked);
        } catch (IllegalArgumentException invalidText) {
            // A half-surrogate or oversize edit is explicitly rejected, never
            // silently replaced by Java's default UTF-8 encoder.
        }
        if (accepted == 0) {
            Toast.makeText(this, "Minyar could not accept this change. Please try again.", Toast.LENGTH_SHORT).show();
            requestFrame(); // Restore the authoritative value after rejection.
            return;
        }
        if (node.kind == 4 || node.kind == 5) pending.put(node.key, accepted);
    }

    private final class MinyarInput extends EditText {
        MinyarInput() { super(MinyarActivity.this); }
        @Override public InputConnection onCreateInputConnection(EditorInfo attributes) {
            InputConnection input = super.onCreateInputConnection(attributes);
            if (input == null) return null;
            return new InputConnectionWrapper(input, false) {
                @Override public void closeConnection() {
                    super.closeConnection();
                    requestFrame();
                }
                @Override public boolean finishComposingText() {
                    boolean result = super.finishComposingText();
                    requestFrame();
                    return result;
                }
                @Override public boolean commitText(CharSequence text, int cursor) {
                    boolean result = super.commitText(text, cursor);
                    requestFrame();
                    return result;
                }
                @Override public boolean setComposingText(CharSequence text, int cursor) {
                    boolean result = super.setComposingText(text, cursor);
                    requestFrame();
                    return result;
                }
            };
        }
    }

    private boolean hasComposition() {
        if (controls != null)
            for (View control : controls)
                if (control instanceof EditText
                    && BaseInputConnection.getComposingSpanStart(((EditText)control).getText()) >= 0) return true;
        return false;
    }

    private View createControl(int index, MinyarSnapshot.Node node) {
        if (node.kind == 6 || node.kind == 7) {
            LinearLayout box = new LinearLayout(this);
            box.setOrientation(node.kind == 6 ? LinearLayout.HORIZONTAL : LinearLayout.VERTICAL);
            return box;
        }
        if (node.kind == 3) {
            Button button = new Button(this);
            button.setOnClickListener(view -> send(index, 1, "", false));
            return button;
        }
        if (node.kind == 4) {
            EditText input = new MinyarInput();
            input.setSingleLine(true);
            input.setImeOptions(EditorInfo.IME_ACTION_DONE);
            input.addTextChangedListener(new TextWatcher() {
                public void beforeTextChanged(CharSequence text, int start, int count, int after) {}
                public void onTextChanged(CharSequence text, int start, int before, int count) {}
                public void afterTextChanged(Editable text) { send(index, 2, text.toString(), false); }
            });
            input.setOnEditorActionListener((view, action, event) -> {
                if (action != EditorInfo.IME_ACTION_DONE) return false;
                send(index, 6, input.getText().toString(), false);
                return true;
            });
            return input;
        }
        if (node.kind == 5) {
            Switch toggle = new Switch(this);
            toggle.setOnCheckedChangeListener((view, checked) -> send(index, 2, "", checked));
            return toggle;
        }
        TextView label = new TextView(this);
        label.setTextSize(node.kind == 2 ? 28 : 18);
        label.setAccessibilityHeading(node.kind == 2);
        return label;
    }

    private void renderLatest() {
        byte[] bytes = nativeSnapshot(token);
        if (bytes == null) return;
        MinyarSnapshot next = MinyarSnapshot.decode(bytes);
        // Equal revisions may contain an authoritative value deferred while
        // composing; IME completion can change spans without changing text.
        if (snapshot != null && next.revision < snapshot.revision) return;
        boolean compatible = next.sameStructure(snapshot);
        // A structural redraw must not replace controls holding newer admitted
        // edits. The worker publishes again after consuming every queued event,
        // including events made stale by an earlier structural change.
        if (!compatible) {
            long waiting = 0;
            for (long sequence : pending.values()) waiting = Math.max(waiting, sequence);
            if (!MinyarSnapshot.mayReplace(waiting, next.appliedEvent, hasComposition())) return;
        }
        applying = true;
        try {
            if (!compatible) {
                pending.clear(); // Every old entry is acknowledged before rebuilding.
                scroll.removeAllViews();
                controls = new View[next.nodes.length];
                boxes = new LinearLayout[next.nodes.length];
                for (int index = 0; index < next.nodes.length; index++) {
                    MinyarSnapshot.Node node = next.nodes[index];
                    View control = createControl(index, node);
                    controls[index] = control;
                    if (node.kind >= 6) boxes[index] = (LinearLayout)control;
                    if (!node.key.isEmpty()) control.setTag(node.key);
                    if (node.kind >= 3 && node.kind <= 5) control.setMinimumHeight(points(48));
                    ViewGroup parent = node.parent == 0 ? scroll : boxes[node.parent - 1];
                    parent.addView(control);
                }
            }
            setTitle(next.title);
            for (int index = 0; index < next.nodes.length; index++) {
                MinyarSnapshot.Node node = next.nodes[index];
                View control = controls[index];
                long waiting = pending.containsKey(node.key) ? pending.get(node.key) : 0;
                if (node.kind >= 6) {
                    LinearLayout box = boxes[index];
                    int padding = points(node.padding);
                    box.setPadding(padding, padding, padding, padding);
                    for (int child = 0; child < box.getChildCount(); child++) {
                        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(
                            node.kind == 7 ? ViewGroup.LayoutParams.MATCH_PARENT : ViewGroup.LayoutParams.WRAP_CONTENT,
                            ViewGroup.LayoutParams.WRAP_CONTENT);
                        if (child != 0) {
                            if (node.kind == 6) layout.leftMargin = points(node.spacing);
                            else layout.topMargin = points(node.spacing);
                        }
                        box.getChildAt(child).setLayoutParams(layout);
                    }
                } else if (node.kind == 4) {
                    EditText input = (EditText)control;
                    boolean composing = BaseInputConnection.getComposingSpanStart(input.getText()) >= 0;
                    if (MinyarSnapshot.mayReplace(waiting, next.appliedEvent, composing)
                        && !input.getText().toString().equals(node.text)) {
                        int start = input.getSelectionStart(), end = input.getSelectionEnd();
                        input.setText(node.text);
                        if (start >= 0 && end >= 0)
                            input.setSelection(Math.min(start, node.text.length()), Math.min(end, node.text.length()));
                    }
                } else if (node.kind == 5) {
                    Switch toggle = (Switch)control;
                    toggle.setText(node.text);
                    if (MinyarSnapshot.mayReplace(waiting, next.appliedEvent, false)) toggle.setChecked(node.checked);
                } else {
                    ((TextView)control).setText(node.text);
                }
                if (waiting <= next.appliedEvent) pending.remove(node.key);
            }
            snapshot = next;
        } finally { applying = false; }
    }
}
