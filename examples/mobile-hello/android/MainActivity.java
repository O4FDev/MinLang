package org.minyar.hello;

import android.app.Activity;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
    static { System.loadLibrary("minyar_hello"); }
    private native int answer();
    private static Integer result;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        // Activity recreation keeps the one-shot native startup result.
        if (result == null) result = answer();
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        int padding = Math.round(24 * getResources().getDisplayMetrics().density);
        column.setPadding(padding, padding, padding, padding);
        TextView title = new TextView(this);
        title.setText("Hello from Minyar");
        title.setTextSize(28);
        column.addView(title);
        TextView value = new TextView(this);
        value.setText("A little Minyar program made " + result + " lights.");
        value.setTextSize(18);
        column.addView(value);
        setContentView(column);
    }
}
