/*
 * File: PlacementOracle.java
 * Modification: 2026-10-12 — independent JDK Random placement cross-check.
 */
import java.util.Random;

public class PlacementOracle {
    private static final long CXM = 341873128712L;
    private static final long CZM = 132897987541L;
    private static int[] candidate(long seed, int rx, int rz, int spacing, int separation, int salt) {
        Random random = new Random(seed + rx * CXM + rz * CZM + salt);
        return new int[] {rx * spacing + random.nextInt(spacing - separation),
                          rz * spacing + random.nextInt(spacing - separation)};
    }
    private static boolean hasVillage(long seed,int cx,int cz) {
        int minx = Math.floorDiv(cx - 10,34),maxx = Math.floorDiv(cx + 10,34);
        int minz = Math.floorDiv(cz - 10,34),maxz = Math.floorDiv(cz + 10,34);
        for(int rx=minx;rx<=maxx;rx++)for(int rz=minz;rz<=maxz;rz++) {
            int[] v=candidate(seed,rx,rz,34,8,10387312);
            if(Math.abs(v[0]-cx)<=10 && Math.abs(v[1]-cz)<=10)return true;
        }
        return false;
    }
    public static void main(String[] args) {
        long seed = Long.parseLong(args[0]);
        int radius = Integer.parseInt(args[1]);
        System.out.println("version,seed,chunk_x,chunk_z,x,z,projected_surface_y,biome_id,classification");
        for(int rz=Math.floorDiv(-radius,512);rz<=Math.floorDiv(radius,512);rz++)
            for(int rx=Math.floorDiv(-radius,512);rx<=Math.floorDiv(radius,512);rx++){
                int[] p=candidate(seed,rx,rz,32,8,165745296);
                int x=p[0]*16, z=p[1]*16;
                if(x < -radius || x > radius || z < -radius || z > radius)continue;
                int i=p[0]>>4,j=p[1]>>4;
                Random r=new Random(((long)(i ^ (j<<4))) ^ seed);
                r.nextInt();
                if(r.nextInt(5)!=0 || hasVillage(seed,p[0],p[1]))continue;
                System.out.printf("1.21.8,%d,%d,%d,%d,%d,unknown,unknown,placement_candidate%n",seed,p[0],p[1],x,z);
            }
    }
}
