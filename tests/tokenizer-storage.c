
#define MINYAR_RC_TESTING
#include "runtime/minyar_runtime.c"
#include <assert.h>
static size_t tokenizer_lists;
MinyarList *probe_tokenizer_list(void) { tokenizer_lists++; return minyar_list_new(); }
extern void tokenize(MinyarText *, MinyarList *, MinyarList *, MinyarList *);
static void drain(void) {
#ifdef MINYAR_BOUNDED_RC
 while(rc_pending_count) minyar_rc_poll(1024);
#endif
 assert(rc_pending_count==0); assert(rc_frames==NULL);
}
int main(int argc,char **argv) {
 assert(argc==2);size_t stable_bytes=0,stable_objects=0;
 for(int pass=0;pass<3;pass++) {
  FILE *f=fopen(argv[1],"rb");assert(f);assert(!fseek(f,0,SEEK_END));long n=ftell(f);assert(n>=0);assert(!fseek(f,0,SEEK_SET));
  unsigned char *bytes=new_bytes(n);assert(fread(bytes,1,(size_t)n,f)==(size_t)n);bytes[n]=0;fclose(f);
  MinyarText *source=new_text(bytes,n,-1);
  MinyarList *kinds=minyar_list_new(),*texts=minyar_list_new(),*lines=minyar_list_new();
  minyar_list_references(texts);minyar_list_references(lines);
  tokenize(source,kinds,texts,lines);
  /* Output owners must survive both source retirement and complete deferred cleanup. */
  minyar_rc_release(source);drain();
  assert(kinds->length==texts->length&&kinds->length==lines->length);
  MinyarText *alias=NULL;unsigned char *expected=NULL;size_t alias_bytes=0;
  for(long long i=0;i<kinds->length;i++) {
   MinyarText *text=(MinyarText *)(intptr_t)texts->values[i],*line=(MinyarText *)(intptr_t)lines->values[i];
   if(pass==0) {printf("%lld\t%.*s\t",kinds->values[i],(int)line->byte_length,line->bytes);for(long long j=0;j<text->byte_length;j++)printf("%02x",text->bytes[j]);putchar('\n');}
   if(!alias&&kinds->values[i]==3) {alias=text;minyar_rc_retain(alias);alias_bytes=(size_t)alias->byte_length;expected=malloc(alias_bytes+1);assert(expected);memcpy(expected,alias->bytes,alias_bytes);}
  }
  minyar_rc_release(kinds);minyar_rc_release(texts);minyar_rc_release(lines);drain();
  if(alias) {assert((size_t)alias->byte_length==alias_bytes);assert(!memcmp(alias->bytes,expected,alias_bytes));free(expected);minyar_rc_release(alias);drain();}
  assert(rc_object_count==rc_immortal_object_count);
  if(pass==0){stable_bytes=rc_bytes;stable_objects=rc_object_count;}else{assert(rc_bytes==stable_bytes);assert(rc_object_count==stable_objects);}
 }
 fprintf(stderr,"TOKEN_LISTS=%zu\n",tokenizer_lists);
 fprintf(stderr,"OWNERS clean=1 retained_objects=%zu retained_bytes=%zu\n",stable_objects,stable_bytes);
}
