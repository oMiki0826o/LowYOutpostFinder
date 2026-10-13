/*
 * File: region_scan.c
 * Modification: 2026-10-13 — standalone low-memory native placement scan slice.
 *
 * Java 48-bit region RNG and structure placement gates only. NO biome, Y or Jigsaw.
 * No Minecraft or third-party dependencies. Standard C11; one thread.
 */
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#define MASK48 UINT64_C(0xffffffffffff)
#define MUL UINT64_C(0x5deece66d)
#define INC UINT64_C(0xb)
#define CELL 512
#define BORDER 29999984

typedef struct {uint64_t state;} RNG;
typedef struct {int cx, cz; uint64_t rank;} Hit;
typedef struct {uint64_t seed, start, count;int xlo,xhi,zlo,zhi,centerx,centerz,top;} Opts;

static int64_t arg_i64(const char *s) {
    errno=0; char *end=NULL; intmax_t n=strtoimax(s,&end,10);
    if(errno || end==s || *end || n<INT64_MIN || n>INT64_MAX) {fprintf(stderr,"bad integer: %s\n",s);exit(2);}
    return (int64_t)n;
}
static uint64_t arg_u64(const char *s) {
    errno=0;char *end=NULL;uintmax_t n=strtoumax(s,&end,10);
    if(errno||end==s||*end||*s=='-'||n>UINT64_MAX){fprintf(stderr,"bad positive integer: %s\n",s);exit(2);}return (uint64_t)n;
}
static int arg_bounded(const char *s,int min,int max){int64_t n=arg_i64(s);if(n<min||n>max){fprintf(stderr,"bounds error: %s\n",s);exit(2);}return (int)n;}
static int floor_div(int a,int b){int q=a/b, r=a%b;return q-(r<0);}
static void set_seed(RNG *r,uint64_t seed){r->state=(seed^MUL)&MASK48;}
static uint32_t bits(RNG *r,int n){r->state=(r->state*MUL+INC)&MASK48;return (uint32_t)(r->state>>(48-n));}
static uint32_t bounded(RNG *r,uint32_t bound){
    if((bound&(bound-1))==0)return (uint32_t)(((uint64_t)bound*bits(r,31))>>31);
    while(1){uint32_t b=bits(r,31),v=b%bound;if((uint64_t)b-v+bound-1<UINT64_C(0x80000000))return v;}
}
static void spread(uint64_t seed,int rx,int rz,int spacing,int sep,int salt,int *cx,int *cz){
    RNG rng;set_seed(&rng,seed+(uint64_t)(int64_t)rx*UINT64_C(341873128712)
                          +(uint64_t)(int64_t)rz*UINT64_C(132897987541)+(uint64_t)salt);
    *cx=rx*spacing+(int)bounded(&rng,(uint32_t)(spacing-sep));
    *cz=rz*spacing+(int)bounded(&rng,(uint32_t)(spacing-sep));
}
static int frequency_ok(uint64_t seed,int cx,int cz){
    uint32_t mix=(uint32_t)(int32_t)floor_div(cx,16)^((uint32_t)(int32_t)floor_div(cz,16)<<4);
    RNG rng;set_seed(&rng,seed^(uint64_t)(int64_t)(int32_t)mix);
    (void)bits(&rng,32);return bounded(&rng,5)==0;
}
static int village_ok(uint64_t seed,int cx,int cz){
    int xmin=floor_div(cx-10,34),xmax=floor_div(cx+10,34);
    int zmin=floor_div(cz-10,34),zmax=floor_div(cz+10,34);
    for(int rz=zmin;rz<=zmax;rz++)for(int rx=xmin;rx<=xmax;rx++){
        int vx,vz;spread(seed,rx,rz,34,8,10387312,&vx,&vz);
        if(abs(vx-cx)<=10&&abs(vz-cz)<=10)return 0;
    }return 1;
}
static uint64_t score(int cx,int cz,int x,int z){
    int64_t dx=(int64_t)cx*16-x, dz=(int64_t)cz*16-z;
    return (uint64_t)(dx*dx+dz*dz);
}
static int cmp(const Hit *a,const Hit *b){
    if(a->rank!=b->rank)return a->rank>b->rank?1:-1;
    if(a->cx!=b->cx)return a->cx>b->cx?1:-1;
    return (a->cz>b->cz)-(a->cz<b->cz);
}
static void push(Hit *a,int *len,int top,Hit hit){
    int n=*len;
    if(n<top){
        int i=n;(*len)++;
        while(i>0){int p=(i-1)/2;if(cmp(&a[p],&hit)>=0)break;a[i]=a[p];i=p;}a[i]=hit;
    }else if(cmp(&hit,&a[0])<0){
        int i=0;
        while(1){int left=2*i+1,right=left+1;if(left>=n)break;
            int worst=left;if(right<n&&cmp(&a[right],&a[left])>0)worst=right;
            if(cmp(&a[worst],&hit)<=0) break;
            a[i]=a[worst];
            i=worst;
        }a[i]=hit;
    }
}
int main(int argc,char **argv){
    Opts o={0,0,0,-BORDER,BORDER,-BORDER,BORDER,0,0,100};int seed_given=0;
    for(int i=1;i<argc;i++){
        const char *key=argv[i];
        if(!strcmp(key,"--help")){puts("region_scan --seed SIGNED64 --start N --count N --top K --x-min MIN --x-max MAX --z-min MIN --z-max MAX --center-x X --center-z Z");return 0;}
        if(i+1>=argc){fprintf(stderr,"missing value: %s\n",key);return 2;}
        const char *v=argv[++i];
        if(!strcmp(key,"--seed")){o.seed=(uint64_t)arg_i64(v);seed_given=1;}
        else if(!strcmp(key,"--start"))o.start=arg_u64(v);
        else if(!strcmp(key,"--count"))o.count=arg_u64(v);
        else if(!strcmp(key,"--top"))o.top=arg_bounded(v,1,10000);
        else if(!strcmp(key,"--x-min"))o.xlo=arg_bounded(v,-BORDER,BORDER);
        else if(!strcmp(key,"--x-max"))o.xhi=arg_bounded(v,-BORDER,BORDER);
        else if(!strcmp(key,"--z-min"))o.zlo=arg_bounded(v,-BORDER,BORDER);
        else if(!strcmp(key,"--z-max"))o.zhi=arg_bounded(v,-BORDER,BORDER);
        else if(!strcmp(key,"--center-x"))o.centerx=arg_bounded(v,-BORDER,BORDER);
        else if(!strcmp(key,"--center-z"))o.centerz=arg_bounded(v,-BORDER,BORDER);
        else {fprintf(stderr,"unknown arg: %s\n",key);return 2;}
    }
    if(!seed_given||o.xlo>o.xhi||o.zlo>o.zhi){fputs("invalid seed or rectangle\n",stderr);return 2;}
    int rx0=floor_div(o.xlo-368,CELL),rx1=floor_div(o.xhi,CELL);
    int rz0=floor_div(o.zlo-368,CELL),rz1=floor_div(o.zhi,CELL);
    uint64_t width=(uint64_t)(rx1-rx0+1),total=width*(uint64_t)(rz1-rz0+1);
    if(o.start>total||o.count>total-o.start||o.count>UINT64_C(5000000)){
        fputs("bad scan range\n",stderr);return 2;
    }
    Hit *heap=malloc((size_t)o.top*sizeof(*heap));
    if(!heap){fputs("out of memory\n",stderr);return 1;}
    int held=0;uint64_t matches=0;
    for(uint64_t idx=o.start;idx<o.start+o.count;idx++){
        int rx=rx0+(int)(idx%width),rz=rz0+(int)(idx/width);
        int cx,cz;spread(o.seed,rx,rz,32,8,165745296,&cx,&cz);
        int x=cx*16,z=cz*16;
        if(x<o.xlo||x>o.xhi||z<o.zlo||z>o.zhi)continue;
        if(!frequency_ok(o.seed,cx,cz)||!village_ok(o.seed,cx,cz))continue;
        matches++;
        Hit hit={cx,cz,score(cx,cz,o.centerx,o.centerz)};
        push(heap,&held,o.top,hit);
    }
    printf("{\"matches\":%" PRIu64 ",\"hits\":[",matches);
    for(int i=0;i<held;i++)printf("%s[%d,%d]",i?",":"",heap[i].cx,heap[i].cz);
    puts("]}");free(heap);return 0;
}
