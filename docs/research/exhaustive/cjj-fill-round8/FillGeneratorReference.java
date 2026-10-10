import java.util.Random;
public class FillGeneratorReference {
 public static void main(String[] args) {
  long[] seeds = {0L,1L,-1L,186643064605892L};
  for (int s=0;s<seeds.length;s++) {
   Random r=new Random(seeds[s]);
   for(int iteration=0;iteration<2048;iteration++) {
    int n=r.ints(1,1024).findFirst().getAsInt();
    boolean b=r.nextBoolean(); byte y=(byte)r.nextInt();
    char c=(char)r.nextInt(); short h=(short)r.nextInt(); int i=r.nextInt(); float f=r.nextFloat();
    char[] chars=new char[n]; short[] shorts=new short[n]; int[] ints=new int[n];
    for(int p=0;p<n;p++){chars[p]=c;shorts[p]=h;ints[p]=i;}
    for(int p=0;p<n;p++)if(chars[p]!=c||shorts[p]!=h||ints[p]!=i)throw new AssertionError(p);
    System.out.println(s+" "+iteration+" "+n+" "+(b?1:0)+" "+y+" "+(int)c+" "+h+" "+i+" "+Float.floatToRawIntBits(f));
   }
  }
 }
}
