/*
 * File: StartProjectionOracle.java
 * Modification: 2026-10-13 — independent JDK reference for start rotation, seed and box center.
 */
import java.util.Random;
public final class StartProjectionOracle {
  public static void main(String[] args) {
    long seed=Long.parseLong(args[0]); int cx=Integer.parseInt(args[1]);
    int cz=Integer.parseInt(args[2]); int sx=Integer.parseInt(args[3]); int sz=Integer.parseInt(args[4]);
    Random r=new Random(seed);long x=r.nextLong(),z=r.nextLong();
    r.setSeed((long)cx*x ^ (long)cz*z ^ seed);
    int rot=r.nextInt(4);
    int a=sx-1,b=sz-1;
    int p=0,q=0;
    switch(rot) {
      case 0: p=a;q=b;break;
      case 1: p=-b;q=a;break;
      case 2: p=-a;q=-b;break;
      case 3: p=b;q=-a;break;
      default:throw new IllegalStateException();
    }
    int px=cx*16,pz=cz*16;
    System.out.print(rot+","+((Math.min(px,px+p)+Math.max(px,px+p))/2)+","+((Math.min(pz,pz+q)+Math.max(pz,pz+q))/2));
  }
}
