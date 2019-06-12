void isort_c(int a[], int n) {
    int k, key, i;
    for (k=1; k<n; ++k) {
        key=a[k];
        i = k-1;
        while ((i >= 0) && (key < a[i])) {
            a[i+1] = a[i];
            --i;
        }
        a[i+1] = key;
    }
}

void isort_faulty(int a[], int n) {
    // gcc figures out at -O1 that the outer loop either runs eternally or never
    int k, key, i;
    for (k=1; k<n; ++n) {
        key=a[k];
        i = k-1;
        while ((i >= 0) && (key < a[i])) {
            a[i+1] = a[i];
            --i;
        }
        a[i+1] = key;
    }
}

int main() {
  int a[11];
  a[0] = 0;
  a[1] = 11; a[2]=10;a[3]=9; a[4]=8; a[5]=7; a[6]=6; a[7]=5;
  a[8] =4; a[9]=3; a[10]=2;

  isort_c(a, 11);
  isort_faulty(a, 11);

  return a[10] == 11;
}


